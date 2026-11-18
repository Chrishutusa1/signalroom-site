"""
signalroom-airtable-bridge — keep Neon in sync with Buzzsprout (the source of truth).

Name kept for continuity; the store is now Neon, not Airtable. The Airtable base
(app3hF8k8ZGXvf9XF) was retired in the 2026-11 sunset because its Public API kept
hitting the monthly quota. This script makes ZERO api.airtable.com calls.

Why this exists
---------------
New Signal Room episodes land in Buzzsprout. This single task keeps the Neon data
layer current from the authoritative Buzzsprout API:
  1. UPSERT rich raw fields into `buzzsprout_episode_data` (the Neon home of the
     retired Airtable "Buzzsprout Episode Data" table), matched on the Buzzsprout
     GUID. Only the Buzzsprout-owned columns are written; transcript / listener /
     language / status / provenance columns set by the one-time seed or other
     processes are left untouched.
  2. CREATE any missing `podcast_episode` hub rows with full Buzzsprout-derived
     fields + a parsed Guest. Existing hub rows are left untouched (manual curation
     + stats/PhraseIntel fields preserved), with two narrow exceptions: a blank
     youtube_video_id is backfilled by the key-gated YouTube Data API resolver, and
     a blank youtube_url is derived deterministically from the Video ID
     (watch?v=<id>, no API key needed). New rows get sync_status 'New - Unverified'
     to flag them for enrichment; their youtube_video_id + youtube_url are auto-filled
     when the resolver finds a confident guest+date match (else left blank).
  3. LINK any buzzsprout_episode_data row to its hub episode (podcast_episode_id FK)
     once the hub row exists.

Run `--dry-run` (default) to preview. Pass `--apply` to write.

Reads secrets from C:\\Users\\PC\\Desktop\\HDSC\\SignalRoom\\.env (BUZZSPROUT_API_TOKEN,
YOUTUBE_API_KEY) and DATABASE_URL (the Neon app_rw role) from the environment, else a
DATABASE_URL= line in that same .env. Neon is reached over the serverless HTTP SQL
endpoint (standard library only — no psql / driver needed), matching this repo's
stdlib-only convention for Python scripts.
"""

import argparse
import html as html_lib
import json
import re
import sys
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

ENV_PATH = Path(r"C:\Users\PC\Desktop\HDSC\SignalRoom\.env")
BZ_PODCAST_ID = "2550733"

# YouTube (full-episode channel; a separate UCPvgS... channel holds shorts/clips)
YT_CHANNEL_ID = "UCk7qyfPFVyJCMsmQHX8b7mw"
YT_MIN_FULL_SECONDS = 600     # >=10 min => treat as a full episode, not a Short/clip
YT_MATCH_DATE_WINDOW = 4      # YT publish must be within N days of Buzzsprout publish
YT_UPLOADS_PAGE_CAP = 6       # max 50-item pages of uploads to scan (covers months)

UA = "signalroom-airtable-bridge/2.0"

# Buzzsprout-owned columns on buzzsprout_episode_data (matched on guid). Everything
# NOT listed here (transcript_raw, unique_listeners, explicit, language,
# buzzsprout_status, notes, transcript_url, chapters, created_at_buzzsprout,
# updated_at_buzzsprout, airtable_id, podcast_episode_id, description) is owned by the
# seed or other processes and is never overwritten by this bridge.
BED_OWNED = [
    "title", "episode_number", "buzzsprout_episode_id", "show_name", "podcast_id",
    "publish_date", "episode_url", "audio_url", "download_url", "duration_seconds",
    "tags", "show_notes_html", "total_plays", "season", "stats_url", "last_api_sync",
    "hq", "magic_mastering", "private", "inactive_at",
]


def load_env():
    try:
        text = ENV_PATH.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        text = ENV_PATH.read_text(encoding="latin-1")
    except OSError:
        return {}
    env = {}
    for line in text.splitlines():
        if line.strip() and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            env[k.strip()] = v.strip().strip('"')
    return env


def http_get(url, headers):
    return json.loads(urllib.request.urlopen(urllib.request.Request(url, headers=headers)).read())


# ---------------- Neon (serverless HTTP SQL endpoint; stdlib only) ----------------

def get_dsn(env):
    import os
    dsn = (os.environ.get("DATABASE_URL") or env.get("DATABASE_URL") or "").strip().strip('"')
    if not dsn:
        raise SystemExit("No DATABASE_URL (environment or SignalRoom\\.env). Cannot reach Neon.")
    return dsn


def _neon_endpoint(dsn):
    m = re.match(r"^postgres(?:ql)?://[^@]+@([^/:?]+)", dsn)
    if not m:
        raise SystemExit("DATABASE_URL is not a postgres connection string")
    return f"https://{m.group(1)}/sql"


def neon_sql(dsn, query, params=None):
    body = json.dumps({"query": query, "params": params or []}).encode()
    req = urllib.request.Request(
        _neon_endpoint(dsn), data=body, method="POST",
        headers={"Neon-Connection-String": dsn, "Content-Type": "application/json",
                 "Neon-Raw-Text-Output": "true", "Neon-Array-Mode": "false"},
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read()).get("rows", [])


def strip_html(s):
    if not s:
        return ""
    s = re.sub(r"<br\s*/?>", " ", s)
    s = re.sub(r"</p>", " ", s)
    s = re.sub(r"<[^>]+>", "", s)
    s = html_lib.unescape(s)
    return re.sub(r"\s+", " ", s).strip()


def parse_guest(title):
    """Title format is 'Episode Title | Guest Name'. Take the segment after the last '|'."""
    if "|" not in title:
        return None
    guest = title.rsplit("|", 1)[1].strip()
    return guest or None


def bz_fetch_episodes(env):
    return http_get(
        f"https://www.buzzsprout.com/api/{BZ_PODCAST_ID}/episodes.json",
        {"Authorization": f"Token token={env['BUZZSPROUT_API_TOKEN']}", "User-Agent": UA},
    )


# ---------------- YouTube Data API (key-gated) ----------------

def yt_get(path, params, key):
    params = {**params, "key": key}
    url = f"https://www.googleapis.com/youtube/v3/{path}?" + urllib.parse.urlencode(params)
    return http_get(url, {"User-Agent": UA})


def yt_uploads_playlist_id(key):
    r = yt_get("channels", {"part": "contentDetails", "id": YT_CHANNEL_ID}, key)
    return r["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]


def iso8601_to_seconds(dur):
    m = re.fullmatch(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", dur or "")
    if not m:
        return 0
    h, mi, s = (int(x) if x else 0 for x in m.groups())
    return h * 3600 + mi * 60 + s


def yt_fetch_full_episode_candidates(key):
    """Return [{id, title, seconds, published_at}] for full-length (>=10min) uploads.
    published_at is the video's publish timestamp (contentDetails.videoPublishedAt)."""
    uploads = yt_uploads_playlist_id(key)
    items, page = [], None
    for _ in range(YT_UPLOADS_PAGE_CAP):
        params = {"part": "snippet,contentDetails", "playlistId": uploads, "maxResults": 50}
        if page:
            params["pageToken"] = page
        r = yt_get("playlistItems", params, key)
        items.extend(r.get("items", []))
        page = r.get("nextPageToken")
        if not page:
            break
    meta = {}
    for it in items:
        vid = it["contentDetails"]["videoId"]
        meta[vid] = {
            "title": it["snippet"]["title"],
            "published_at": it["contentDetails"].get("videoPublishedAt")
                             or it["snippet"].get("publishedAt", ""),
        }
    durations = {}
    ids = list(meta)
    for i in range(0, len(ids), 50):
        batch = ids[i:i + 50]
        r = yt_get("videos", {"part": "contentDetails", "id": ",".join(batch)}, key)
        for v in r.get("items", []):
            durations[v["id"]] = iso8601_to_seconds(v["contentDetails"].get("duration"))
    out = []
    for vid, m in meta.items():
        secs = durations.get(vid, 0)
        if secs >= YT_MIN_FULL_SECONDS:
            out.append({"id": vid, "title": m["title"], "seconds": secs,
                        "published_at": (m["published_at"] or "")[:10]})
    return out


# Honorifics/credentials stripped from a guest name before token-matching
_GUEST_DROP = {"dr", "mr", "mrs", "ms", "prof", "md", "phd", "mba", "rn", "mph",
               "msn", "dnp", "jd", "esq", "jr", "sr", "ii", "iii", "iv"}


def guest_tokens(guest):
    s = re.sub(r"[^a-z0-9 ]", " ", (guest or "").lower())
    return {t for t in s.split() if t and t not in _GUEST_DROP and len(t) > 1}


def _title_tokens(s):
    s = re.sub(r"[^a-z0-9 ]", " ", (s or "").lower())
    return {t for t in s.split() if t}


def _days_apart(a, b):
    try:
        return abs((date.fromisoformat(a[:10]) - date.fromisoformat(b[:10])).days)
    except Exception:
        return 999


def resolve_yt_video_id(ep_title, guest, ep_pub_date, candidates):
    """Match an episode to its full-length YouTube video by GUEST NAME + PUBLISH-DATE
    proximity — NOT by title (this channel re-headlines episodes on YouTube, so titles
    diverge). Requires every guest name token to appear in the YT title AND the YT
    publish date within YT_MATCH_DATE_WINDOW days of the Buzzsprout publish date.
    Among qualifiers, prefer the closest date, then the longest video.
    Returns (video_id, day_diff, reason)."""
    g = guest_tokens(guest)
    if not g:
        return None, None, "no-guest-to-match"
    if not ep_pub_date:
        return None, None, "no-episode-date"
    best = None  # (id, day_diff, seconds)
    for c in candidates:
        if not g <= _title_tokens(c["title"]):
            continue
        if not c.get("published_at"):
            continue
        dd = _days_apart(c["published_at"], ep_pub_date)
        if dd <= YT_MATCH_DATE_WINDOW:
            if best is None or (dd, -c.get("seconds", 0)) < (best[1], -best[2]):
                best = (c["id"], dd, c.get("seconds", 0))
    if best:
        return best[0], best[1], "guest+date"
    return None, None, "no-confident-match"


# ---------------- field builders (Neon columns) ----------------

def build_bed_row(e):
    """Buzzsprout-owned columns for buzzsprout_episode_data (keyed on guid). Mirrors the
    former Airtable build_bed_patch. Excludes description (zap/seed-owned) and guid
    (the match key)."""
    audio = e.get("audio_url")
    return {
        "title": e.get("title"),
        "episode_number": e.get("episode_number"),
        "buzzsprout_episode_id": str(e["id"]) if e.get("id") is not None else None,
        "show_name": e.get("artist"),
        "podcast_id": BZ_PODCAST_ID,
        "publish_date": e["published_at"][:10] if e.get("published_at") else None,
        "episode_url": e.get("custom_url"),
        "audio_url": audio,
        "download_url": audio,
        "duration_seconds": e.get("duration"),
        "tags": e.get("tags") or None,
        "show_notes_html": e.get("description") or None,
        "total_plays": e.get("total_plays"),
        "season": e.get("season_number"),
        "stats_url": f"https://www.buzzsprout.com/{BZ_PODCAST_ID}/episodes/{e['id']}",
        "last_api_sync": date.today().isoformat(),
        "hq": bool(e.get("hq")),
        "magic_mastering": bool(e.get("magic_mastering")),
        "private": bool(e.get("private")),
        "inactive_at": e.get("inactive_at") or None,
    }


def build_pe_create(e, yt_id=None, *, now=None):
    """Full podcast_episode hub row (missing-episode create). PhraseIntel/keyword fields
    left blank (owned by other processes); sync_status 'New - Unverified' flags the row
    as auto-created. youtube_video_id is filled when the resolver is confident, else blank.
    Raw Buzzsprout detail (show notes html, tags, total plays) lives in
    buzzsprout_episode_data, not the hub."""
    f = {
        "episode_number": e.get("episode_number"),
        "title": e["title"],
        "guest_name": parse_guest(e["title"]),
        "buzzsprout_episode_id": str(e["id"]),
        "buzzsprout_url": f"https://www.buzzsprout.com/{BZ_PODCAST_ID}/episodes/{e['id']}",
        "description": strip_html(e.get("description")),
        "publish_date": None,
        "youtube_video_id": None,
        "youtube_url": None,
        "sync_status": "New - Unverified",
    }
    if e.get("published_at"):
        release = datetime.fromisoformat(e["published_at"].replace("Z", "+00:00"))
        if release.tzinfo is None:
            raise ValueError("Buzzsprout publication date must include a timezone")
        if not e.get("private", False) and release <= (now or datetime.now(timezone.utc)):
            f["publish_date"] = e["published_at"][:10]
    if yt_id:
        f["youtube_video_id"] = yt_id
        f["youtube_url"] = f"https://www.youtube.com/watch?v={yt_id}"
    return f


# ---------------- Neon writers ----------------

def bed_upsert(dsn, row, guid):
    cols = ["guid"] + BED_OWNED
    vals = [guid] + [_param(row.get(c)) for c in BED_OWNED]
    placeholders = ", ".join(f"${i + 1}" for i in range(len(cols)))
    updates = ", ".join(f"{c} = excluded.{c}" for c in BED_OWNED)
    sql = (f"insert into buzzsprout_episode_data ({', '.join(cols)}) "
           f"values ({placeholders}) "
           f"on conflict (guid) do update set {updates}, updated_at = now()")
    neon_sql(dsn, sql, vals)


def pe_insert(dsn, f):
    cols = ["episode_number", "title", "guest_name", "buzzsprout_episode_id",
            "buzzsprout_url", "description", "publish_date", "youtube_video_id",
            "youtube_url", "sync_status"]
    vals = [_param(f.get(c)) for c in cols]
    placeholders = ", ".join(f"${i + 1}" for i in range(len(cols)))
    sql = (f"insert into podcast_episode ({', '.join(cols)}) "
           f"values ({placeholders}) "
           f"on conflict (show, season, episode_number) do nothing")
    neon_sql(dsn, sql, vals)


def pe_backfill_yt(dsn, row_id, fields):
    sets = ", ".join(f"{k} = ${i + 2}" for i, k in enumerate(fields))
    vals = [row_id] + [_param(v) for v in fields.values()]
    neon_sql(dsn, f"update podcast_episode set {sets}, updated_at = now() where id = $1", vals)


def _param(v):
    """Normalise to a text/None param the Neon column can cast (Neon-Raw-Text-Output)."""
    if v is None:
        return None
    if isinstance(v, bool):
        return "true" if v else "false"
    return str(v)


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--dry-run", action="store_true", help="preview only (default)")
    g.add_argument("--apply", action="store_true", help="write changes to Neon")
    args = ap.parse_args()
    apply = args.apply
    mode = "APPLY" if apply else "DRY-RUN"

    env = load_env()
    dsn = get_dsn(env)
    print(f"[{date.today().isoformat()}] signalroom-airtable-bridge ({mode}) -> Neon")

    eps = bz_fetch_episodes(env)
    eps = [e for e in eps if not e.get("private") and not e.get("inactive_at")]
    print(f"  Buzzsprout API: {len(eps)} public episodes")

    # ---- 1. buzzsprout_episode_data: upsert Buzzsprout-owned fields (match on guid) ----
    bed_have = {r["guid"] for r in neon_sql(dsn, "select guid from buzzsprout_episode_data")}
    bed_create = sum(1 for e in eps if e["guid"] not in bed_have)
    bed_update = len(eps) - bed_create
    print(f"  buzzsprout_episode_data: {bed_update} to refresh, {bed_create} to create")

    # ---- 2. YouTube: resolve full-episode video IDs (key-gated) ----
    yt_candidates = None
    yt_key = env.get("YOUTUBE_API_KEY")
    if yt_key:
        try:
            yt_candidates = yt_fetch_full_episode_candidates(yt_key)
            print(f"  YouTube: {len(yt_candidates)} full-length (>={YT_MIN_FULL_SECONDS}s) channel videos fetched")
        except Exception as ex:
            print(f"  YouTube: resolver skipped — fetch failed ({ex})")
            yt_candidates = None
    else:
        print("  YouTube: resolver skipped — no YOUTUBE_API_KEY in .env (IDs left blank)")

    def resolve(title, guest, pub_date):
        if not yt_candidates:
            return None, None, "no-key"
        return resolve_yt_video_id(title, guest, pub_date, yt_candidates)

    # ---- 3. podcast_episode: create missing (with YT id) ----
    pe_rows = neon_sql(dsn, "select id, episode_number, buzzsprout_episode_id, title, "
                            "guest_name, publish_date, youtube_video_id, youtube_url "
                            "from podcast_episode")
    pe_have = {str(r["buzzsprout_episode_id"]) for r in pe_rows if r.get("buzzsprout_episode_id")}
    pe_creates = []
    for e in eps:
        if str(e["id"]) in pe_have:
            continue
        pub = e["published_at"][:10] if e.get("published_at") else None
        vid, dd, reason = resolve(e["title"], parse_guest(e["title"]), pub)
        pe_creates.append((build_pe_create(e, vid), (vid, dd, reason)))
    print(f"  podcast_episode: {len(pe_rows)} existing, {len(pe_creates)} to create")
    for f, (vid, dd, reason) in pe_creates:
        ytnote = f"YT={vid} (+{dd}d)" if vid else f"YT=none ({reason})"
        print(f"      + EP {f['episode_number']}  BZ {f['buzzsprout_episode_id']}  "
              f"guest={f['guest_name']!r}  {ytnote}  {str(f['title'])[:46]}")

    # ---- 4. podcast_episode: backfill YouTube on existing rows ----
    #   (a) blank youtube_video_id -> resolve via the key-gated resolver
    #   (b) youtube_video_id present but youtube_url blank -> derive the URL (no key)
    pe_yt_patches = []
    for r in pe_rows:
        if not r.get("title"):
            continue
        vid = r.get("youtube_video_id")
        fields = {}
        if not vid and yt_candidates:
            rvid, dd, reason = resolve(r["title"], r.get("guest_name"), r.get("publish_date"))
            if rvid:
                vid = rvid
                fields["youtube_video_id"] = rvid
                print(f"      ~ fill YT id on EP {r.get('episode_number')} BZ {r.get('buzzsprout_episode_id')}: "
                      f"{rvid} (+{dd}d)  guest={r.get('guest_name')!r}  {str(r['title'])[:40]}")
            else:
                print(f"      · no YT match for EP {r.get('episode_number')} BZ {r.get('buzzsprout_episode_id')} "
                      f"({reason})  guest={r.get('guest_name')!r}")
        if vid and not r.get("youtube_url"):
            fields["youtube_url"] = f"https://www.youtube.com/watch?v={vid}"
            print(f"      ~ fill YT url on EP {r.get('episode_number')}: watch?v={vid}")
        if fields:
            pe_yt_patches.append((r["id"], fields))
    print(f"  podcast_episode: {len(pe_yt_patches)} existing rows to backfill (YT id/url)")

    if not apply:
        print("\n  DRY-RUN — no changes written. Re-run with --apply to commit.")
        return

    for e in eps:
        bed_upsert(dsn, build_bed_row(e), e["guid"])
    for f, _meta in pe_creates:
        pe_insert(dsn, f)
    for row_id, fields in pe_yt_patches:
        pe_backfill_yt(dsn, row_id, fields)
    # ---- 5. link buzzsprout_episode_data rows to their hub episode (FK) ----
    linked = neon_sql(dsn,
        "update buzzsprout_episode_data b set podcast_episode_id = p.id, updated_at = now() "
        "from podcast_episode p "
        "where p.buzzsprout_episode_id = b.buzzsprout_episode_id "
        "and b.podcast_episode_id is distinct from p.id "
        "returning b.id")
    print(f"\n  APPLIED: buzzsprout_episode_data {len(eps)} upserted; "
          f"podcast_episode {len(pe_creates)} created, {len(pe_yt_patches)} YT-backfilled; "
          f"{len(linked)} BED rows (re)linked to a hub episode.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"BRIDGE FAILED: {e}", file=sys.stderr)
        raise
