"""
signalroom-airtable-bridge — keep Airtable in sync with Buzzsprout (the source of truth).

Why this exists
---------------
The Zapier zap "Buzzsprout RSS -> Airtable (new episodes)" only writes a BARE row
into `Buzzsprout Episode Data` (Episode GUID / Title / Description / Publish Date).
The rich enrichment of that table was a one-shot manual pipeline (BuzzsproutData/
build_records.js) that last ran 2026-05-08 and was never repeated. And the
`Podcast Episodes` table (which the website-add workflow + stats sync read) is
populated 100% manually and stalled at EP 27 (2026-04-30).

This single task fixes BOTH gaps from the authoritative Buzzsprout API:
  1. UPSERT rich fields into `Buzzsprout Episode Data` (fills the bare zap rows,
     refreshes plays + Last API Sync). Idempotent; matches build_records.js mapping.
  2. CREATE any missing `Podcast Episodes` rows with full Buzzsprout-derived fields
     + a parsed Guest. Existing Podcast Episodes rows are left untouched (manual
     curation + the stats-sync/PhraseIntel fields are preserved), with two narrow
     exceptions: a blank `YouTube Video ID` is backfilled by the key-gated YouTube
     Data API resolver, and a blank `YouTube URL` is derived deterministically from
     the Video ID (watch?v=<id>, no API key needed). New rows are created with blank
     Sync Status to flag them for enrichment; their `YouTube Video ID` + `YouTube URL`
     are auto-filled when the resolver finds a confident guest+date match (else left
     blank for manual entry).

Run `--dry-run` (default) to preview. Pass `--apply` to write.

Reads secrets from C:\\Users\\PC\\Desktop\\HDSC\\SignalRoom\\.env
"""

import argparse
import html as html_lib
import json
import re
import sys
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

ENV_PATH = Path(r"C:\Users\PC\Desktop\HDSC\SignalRoom\.env")
BASE_ID = "app3hF8k8ZGXvf9XF"
BZ_PODCAST_ID = "2550733"

BED_TABLE = "tblrji2ivwJQYE6Rg"   # Buzzsprout Episode Data
PE_TABLE = "tblzKDGrxDnhFqQUU"    # Podcast Episodes

# YouTube (full-episode channel; a separate UCPvgS... channel holds shorts/clips)
YT_CHANNEL_ID = "UCk7qyfPFVyJCMsmQHX8b7mw"
YT_MIN_FULL_SECONDS = 600     # >=10 min => treat as a full episode, not a Short/clip
YT_MATCH_DATE_WINDOW = 4      # YT publish must be within N days of Buzzsprout publish
YT_UPLOADS_PAGE_CAP = 6       # max 50-item pages of uploads to scan (covers months)

# Buzzsprout Episode Data field IDs (from BuzzsproutData/build_records.js)
BED = {
    "title": "fldTGlKXxQuejzxOm",
    "episodeNumber": "fldc6eACSh6IuzeNu",
    "guid": "fld38bSF5l4VPUZIM",
    "buzzId": "fldr177dnslG8yp4J",
    "showName": "fldtT1hpQdwTPCa8B",
    "podcastId": "fldnhMyI5rkeCLlgZ",
    "publishDate": "fldeZSpz11PlJ9jFx",
    "episodeUrl": "fldvP7nmmqGacT3bv",
    "audioUrl": "fldUgZLaa4Ol9uH9n",
    "downloadUrl": "fldwDvXo1pSRZeuar",
    "duration": "fldRFq70OF7av7FOu",
    "tags": "fldVJY6wSdkATTpB6",
    "artwork": "fldPSknx2ypJbfD2s",
    "showNotesHtml": "fldulzgwsmWPPkNVd",
    "totalPlays": "fldceXO1rMxL98hG3",
    "season": "fldznPRPBvulpn592",
    "statsUrl": "fldiJWXKqhxWVbjdH",
    "lastSync": "fldL36O3CsGmgbftx",
    "hq": "fldAVuukey9gH0751",
    "magicMastering": "fldPPa0YkAnLeukkK",
    "private": "fld1fcx4tXHhAvDwI",
    "inactiveAt": "fld4wj27giILXAnMX",
}

UA = "signalroom-airtable-bridge/1.0"


def load_env():
    try:
        text = ENV_PATH.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        text = ENV_PATH.read_text(encoding="latin-1")
    env = {}
    for line in text.splitlines():
        if line.strip() and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            env[k.strip()] = v.strip().strip('"')
    return env


def http_get(url, headers):
    return json.loads(urllib.request.urlopen(urllib.request.Request(url, headers=headers)).read())


def http_send(url, body, headers, method):
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(),
        headers={**headers, "Content-Type": "application/json"}, method=method,
    )
    return json.loads(urllib.request.urlopen(req).read())


def bz_fetch_episodes(env):
    return http_get(
        f"https://www.buzzsprout.com/api/{BZ_PODCAST_ID}/episodes.json",
        {"Authorization": f"Token token={env['BUZZSPROUT_API_TOKEN']}", "User-Agent": UA},
    )


def at_list(env, table, by_id=False):
    headers = {"Authorization": f"Bearer {env['AIRTABLE_API_KEY']}"}
    records, offset = [], None
    while True:
        url = f"https://api.airtable.com/v0/{BASE_ID}/{table}?pageSize=100"
        if by_id:
            url += "&returnFieldsByFieldId=true"
        if offset:
            url += f"&offset={offset}"
        r = http_get(url, headers)
        records.extend(r["records"])
        offset = r.get("offset")
        if not offset:
            break
    return records


def at_patch(env, table, updates):
    headers = {"Authorization": f"Bearer {env['AIRTABLE_API_KEY']}"}
    url = f"https://api.airtable.com/v0/{BASE_ID}/{table}"
    for i in range(0, len(updates), 10):
        http_send(url, {"records": updates[i:i + 10]}, headers, "PATCH")


def at_create(env, table, creates):
    headers = {"Authorization": f"Bearer {env['AIRTABLE_API_KEY']}"}
    url = f"https://api.airtable.com/v0/{BASE_ID}/{table}"
    for i in range(0, len(creates), 10):
        http_send(url, {"records": creates[i:i + 10]}, headers, "POST")


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
            cand = (c["id"], dd, c.get("seconds", 0))
            if best is None or (dd, -c.get("seconds", 0)) < (best[1], -best[2]):
                best = cand
    if best:
        return best[0], best[1], "guest+date"
    return None, None, "no-confident-match"


def build_bed_patch(e):
    """Rich fields for Buzzsprout Episode Data (mirrors build_records.js). Excludes
    Episode Description (the zap already sets it from RSS) and Episode GUID (the match key)."""
    f = {}
    if e.get("title"):
        f[BED["title"]] = e["title"]
    if e.get("episode_number") is not None:
        f[BED["episodeNumber"]] = e["episode_number"]
    if e.get("id") is not None:
        f[BED["buzzId"]] = str(e["id"])
    if e.get("artist"):
        f[BED["showName"]] = e["artist"]
    f[BED["podcastId"]] = BZ_PODCAST_ID
    if e.get("published_at"):
        f[BED["publishDate"]] = e["published_at"][:10]
    if e.get("custom_url"):
        f[BED["episodeUrl"]] = e["custom_url"]
    if e.get("audio_url"):
        f[BED["audioUrl"]] = e["audio_url"]
        f[BED["downloadUrl"]] = e["audio_url"]
    if e.get("duration") is not None:
        f[BED["duration"]] = e["duration"]
    if e.get("tags"):
        f[BED["tags"]] = e["tags"]
    if e.get("description"):
        f[BED["showNotesHtml"]] = e["description"]
    if e.get("total_plays") is not None:
        f[BED["totalPlays"]] = e["total_plays"]
    if e.get("season_number") is not None:
        f[BED["season"]] = e["season_number"]
    f[BED["statsUrl"]] = f"https://www.buzzsprout.com/{BZ_PODCAST_ID}/episodes/{e['id']}"
    f[BED["lastSync"]] = date.today().isoformat()
    f[BED["hq"]] = bool(e.get("hq"))
    f[BED["magicMastering"]] = bool(e.get("magic_mastering"))
    f[BED["private"]] = bool(e.get("private"))
    if e.get("inactive_at"):
        f[BED["inactiveAt"]] = e["inactive_at"]
    return f


def build_pe_create(e, yt_id=None):
    """Full Podcast Episodes record (by field NAME). PhraseIntel/Sync Status left blank
    (owned by other processes; blank Sync Status flags the row as auto-created). YouTube
    Video ID is filled when the key-gated resolver finds a confident match, else blank."""
    f = {
        "Episode Title": e["title"],
        "Episode Number": e.get("episode_number"),
        "Buzzsprout Episode ID": str(e["id"]),
        "Publish Date": e["published_at"][:10] if e.get("published_at") else None,
        "Episode Description": strip_html(e.get("description")),
        "Buzzsprout Show Notes HTML": e.get("description") or "",
        "Buzzsprout Tags": e.get("tags") or "",
        "Tags": e.get("tags") or "",
        "Buzzsprout URL": f"https://www.buzzsprout.com/{BZ_PODCAST_ID}/episodes/{e['id']}",
        "Buzzsprout Total Plays": e.get("total_plays"),
        "Guest": parse_guest(e["title"]),
    }
    if yt_id:
        f["YouTube Video ID"] = yt_id
        f["YouTube URL"] = f"https://www.youtube.com/watch?v={yt_id}"
    return f


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--dry-run", action="store_true", help="preview only (default)")
    g.add_argument("--apply", action="store_true", help="write changes to Airtable")
    args = ap.parse_args()
    apply = args.apply
    mode = "APPLY" if apply else "DRY-RUN"

    env = load_env()
    print(f"[{date.today().isoformat()}] signalroom-airtable-bridge ({mode})")

    eps = bz_fetch_episodes(env)
    eps = [e for e in eps if not e.get("private") and not e.get("inactive_at")]
    by_guid = {e["guid"]: e for e in eps}
    by_id = {str(e["id"]): e for e in eps}
    print(f"  Buzzsprout API: {len(eps)} public episodes")

    # ---- 1. Buzzsprout Episode Data: upsert rich fields ----
    bed_rows = at_list(env, BED_TABLE, by_id=True)
    bed_by_guid = {r["fields"].get(BED["guid"]): r for r in bed_rows}
    bed_patches, bed_creates = [], []
    for e in eps:
        patch = build_bed_patch(e)
        existing = bed_by_guid.get(e["guid"])
        if existing:
            # only patch if something is actually missing/changed (avoid no-op churn on play counts is fine)
            cur = existing["fields"]
            changed = {k: v for k, v in patch.items() if cur.get(k) != v}
            if changed:
                bed_patches.append({"id": existing["id"], "fields": changed})
        else:
            create = dict(patch)
            create[BED["guid"]] = e["guid"]
            bed_creates.append({"fields": create})
    print(f"  Buzzsprout Episode Data: {len(bed_patches)} to patch, {len(bed_creates)} to create")

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

    # ---- 3. Podcast Episodes: create missing (with YT id) ----
    pe_rows = at_list(env, PE_TABLE)
    pe_have = {str(r["fields"].get("Buzzsprout Episode ID")) for r in pe_rows
               if r["fields"].get("Buzzsprout Episode ID")}
    pe_creates = []
    for e in eps:
        if str(e["id"]) in pe_have:
            continue
        pub = e["published_at"][:10] if e.get("published_at") else None
        vid, dd, reason = resolve(e["title"], parse_guest(e["title"]), pub)
        pe_creates.append({"fields": build_pe_create(e, vid), "_yt": (vid, dd, reason)})
    print(f"  Podcast Episodes: {len(pe_rows)} existing, {len(pe_creates)} to create")
    for c in pe_creates:
        f = c["fields"]
        vid, dd, reason = c["_yt"]
        ytnote = f"YT={vid} (+{dd}d)" if vid else f"YT=none ({reason})"
        print(f"      + EP {f['Episode Number']}  BZ {f['Buzzsprout Episode ID']}  "
              f"guest={f['Guest']!r}  {ytnote}  {f['Episode Title'][:46]}")
    for c in pe_creates:
        c.pop("_yt", None)

    # ---- 4. Podcast Episodes: backfill YouTube on existing rows ----
    #   (a) blank Video ID  -> resolve via the key-gated resolver (needs candidates)
    #   (b) Video ID present but YouTube URL blank -> derive the URL deterministically
    #       from the id (no API key required)
    pe_yt_patches = []
    for r in pe_rows:
        f = r["fields"]
        if not f.get("Episode Title"):
            continue
        vid = f.get("YouTube Video ID")
        fields = {}
        if not vid and yt_candidates:
            rvid, dd, reason = resolve(f["Episode Title"], f.get("Guest"), f.get("Publish Date"))
            if rvid:
                vid = rvid
                fields["YouTube Video ID"] = rvid
                print(f"      ~ fill YT id on EP {f.get('Episode Number')} BZ {f.get('Buzzsprout Episode ID')}: "
                      f"{rvid} (+{dd}d)  guest={f.get('Guest')!r}  {str(f['Episode Title'])[:40]}")
            else:
                print(f"      · no YT match for EP {f.get('Episode Number')} BZ {f.get('Buzzsprout Episode ID')} "
                      f"({reason})  guest={f.get('Guest')!r}")
        if vid and not f.get("YouTube URL"):
            fields["YouTube URL"] = f"https://www.youtube.com/watch?v={vid}"
            print(f"      ~ fill YT url on EP {f.get('Episode Number')}: watch?v={vid}")
        if fields:
            pe_yt_patches.append({"id": r["id"], "fields": fields})
    print(f"  Podcast Episodes: {len(pe_yt_patches)} existing rows to backfill (YT id/url)")

    if not apply:
        print("\n  DRY-RUN — no changes written. Re-run with --apply to commit.")
        return

    if bed_patches:
        at_patch(env, BED_TABLE, bed_patches)
    if bed_creates:
        at_create(env, BED_TABLE, bed_creates)
    if pe_creates:
        at_create(env, PE_TABLE, pe_creates)
    if pe_yt_patches:
        at_patch(env, PE_TABLE, pe_yt_patches)
    print(f"\n  APPLIED: BED {len(bed_patches)} patched / {len(bed_creates)} created; "
          f"Podcast Episodes {len(pe_creates)} created, {len(pe_yt_patches)} YT-backfilled.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"BRIDGE FAILED: {e}", file=sys.stderr)
        raise
