#!/usr/bin/env python3
"""One-time seed of Neon `buzzsprout_episode_data` from the 2026-11-03 Airtable backup.

Loads the retired Airtable "Buzzsprout Episode Data" table
(app3hF8k8ZGXvf9XF / tblrji2ivwJQYE6Rg) into the Neon table created by
db/migrations/srsite_001_buzzsprout_episode_data.sql. Idempotent: upserts on the
Episode GUID, so re-running refreshes rather than duplicates. Carries the Airtable
record id as provenance (airtable_id) and links each row to podcast_episode by
Buzzsprout episode id (podcast_episode_id FK) where a hub row exists.

  python scripts/seed_buzzsprout_episode_data.py --backup-dir "<dir>"            # dry run (default)
  python scripts/seed_buzzsprout_episode_data.py --backup-dir "<dir>" --apply    # write to Neon

<dir> is the per-table backup folder, e.g.
  C:\\Users\\PC\\Documents\\AirtableBackups\\2026-11-03\\Content Intelligence Hub\\tblrji2ivwJQYE6Rg Buzzsprout Episode Data

Neon DSN (the app_rw role) is read from env DATABASE_URL, else a DATABASE_URL= line in
C:\\Users\\PC\\Desktop\\HDSC\\SignalRoom\\.env. Reads Neon over the serverless HTTP SQL
endpoint (stdlib only; no psql/driver needed). Makes ZERO api.airtable.com calls.
"""

import argparse
import json
import re
import sys
import urllib.request
from pathlib import Path

ENV_PATH = Path(r"C:\Users\PC\Desktop\HDSC\SignalRoom\.env")

# Airtable field id -> Neon column (from the backup schema.json for tblrji2ivwJQYE6Rg)
FIELD_MAP = {
    "fldTGlKXxQuejzxOm": "title",
    "fldc6eACSh6IuzeNu": "episode_number",
    "fld38bSF5l4VPUZIM": "guid",
    "fldr177dnslG8yp4J": "buzzsprout_episode_id",
    "fldtT1hpQdwTPCa8B": "show_name",
    "fldnhMyI5rkeCLlgZ": "podcast_id",
    "fldeZSpz11PlJ9jFx": "publish_date",
    "fldvP7nmmqGacT3bv": "episode_url",
    "fldUgZLaa4Ol9uH9n": "audio_url",
    "fldRFq70OF7av7FOu": "duration_seconds",
    "fld2CTZ5OOY9EsFcG": "description",
    "fldVJY6wSdkATTpB6": "tags",
    "fldPSknx2ypJbfD2s": "artwork_url",          # multipleAttachments -> first .url
    "fldtf8diR1G1zNEVp": "transcript_raw",
    "fldV6weQSeYsghEeq": "transcript_source",
    "flduhXst0FQXH9Pnz": "chapters",
    "fldceXO1rMxL98hG3": "total_plays",
    "fldAdWCcIV0qwyZzK": "unique_listeners",
    "fldwDvXo1pSRZeuar": "download_url",
    "fldOYYFJ6LU7ODAB8": "explicit",
    "fldznPRPBvulpn592": "season",
    "fldiJWXKqhxWVbjdH": "stats_url",
    "fldulzgwsmWPPkNVd": "show_notes_html",
    "fldeyAP4uqkhQ546d": "created_at_buzzsprout",
    "fldWPrQbn4x5CJbNd": "updated_at_buzzsprout",
    "fldfGabm71uX0luLa": "language",
    "fldqCQT5kFJuVjHlV": "buzzsprout_status",
    "fldL36O3CsGmgbftx": "last_api_sync",
    "fldIuplihOrTzOl2t": "notes",
    "fldAVuukey9gH0751": "hq",
    "fldPPa0YkAnLeukkK": "magic_mastering",
    "fld1fcx4tXHhAvDwI": "private",
    "fld4wj27giILXAnMX": "inactive_at",
    "fldhwh7XJrxEFE4P1": "transcript_url",
}

INT_COLS = {"episode_number", "duration_seconds", "total_plays", "unique_listeners", "season"}
BOOL_COLS = {"hq", "magic_mastering", "private"}

# Column order for the parameterized upsert (excludes id/created_at/updated_at defaults).
COLS = [
    "airtable_id", "guid", "buzzsprout_episode_id", "podcast_episode_id", "episode_number",
    "title", "show_name", "podcast_id", "publish_date", "episode_url", "audio_url",
    "download_url", "duration_seconds", "description", "show_notes_html", "tags",
    "artwork_url", "transcript_raw", "transcript_source", "transcript_url", "chapters",
    "total_plays", "unique_listeners", "explicit", "season", "language", "buzzsprout_status",
    "stats_url", "notes", "hq", "magic_mastering", "private", "created_at_buzzsprout",
    "updated_at_buzzsprout", "inactive_at", "last_api_sync",
]


def database_url():
    import os
    v = os.environ.get("DATABASE_URL")
    if v:
        return v.strip()
    try:
        for line in ENV_PATH.read_text(encoding="utf-8", errors="replace").splitlines():
            m = re.match(r"\s*DATABASE_URL\s*=\s*(.+)", line)
            if m:
                return m.group(1).strip().strip('"')
    except OSError:
        pass
    raise SystemExit("No DATABASE_URL (env var or SignalRoom\\.env). Cannot reach Neon.")


def neon_endpoint(dsn):
    m = re.match(r"^postgres(?:ql)?://[^@]+@([^/:?]+)", dsn)
    if not m:
        raise SystemExit("DATABASE_URL is not a postgres connection string")
    return f"https://{m.group(1)}/sql"


def neon_sql(dsn, query, params=None):
    body = json.dumps({"query": query, "params": params or []}).encode()
    req = urllib.request.Request(
        neon_endpoint(dsn), data=body, method="POST",
        headers={"Neon-Connection-String": dsn, "Content-Type": "application/json",
                 "Neon-Raw-Text-Output": "true", "Neon-Array-Mode": "false"},
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read()).get("rows", [])


def coerce(col, val):
    """Normalise an Airtable value to a text/None param the Neon column can cast."""
    if val is None or val == "" or val == []:
        return None
    if col == "artwork_url":
        if isinstance(val, list) and val:
            return val[0].get("url")
        return None
    if col in BOOL_COLS:
        return "true" if bool(val) else "false"
    if col in INT_COLS:
        try:
            return str(int(val))
        except (TypeError, ValueError):
            return None
    if isinstance(val, (dict, list)):
        return json.dumps(val)
    return str(val)


def build_row(rec, pe_by_bzid):
    f = rec.get("fields", {})
    out = {c: None for c in COLS}
    out["airtable_id"] = rec.get("id")
    for fid, col in FIELD_MAP.items():
        if fid in f:
            out[col] = coerce(col, f[fid])
    bzid = out.get("buzzsprout_episode_id")
    # A few bare backup rows (the newest episodes) carry no Episode GUID field.
    # Buzzsprout's GUID is deterministically "Buzzsprout-<id>" (verified across every
    # row that has both), so synthesise it rather than drop a real episode.
    if not out.get("guid") and bzid:
        out["guid"] = f"Buzzsprout-{bzid}"
    out["podcast_episode_id"] = pe_by_bzid.get(str(bzid)) if bzid else None
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backup-dir", required=True,
                    help="per-table backup folder containing records.json")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--dry-run", action="store_true", help="preview only (default)")
    g.add_argument("--apply", action="store_true", help="write to Neon")
    args = ap.parse_args()
    apply = args.apply

    backup = Path(args.backup_dir)
    records = json.loads((backup / "records.json").read_text(encoding="utf-8"))["records"]
    print(f"Backup: {len(records)} Buzzsprout Episode Data records in {backup.name}")

    dsn = database_url()
    pe = neon_sql(dsn, "select id, buzzsprout_episode_id from podcast_episode "
                       "where buzzsprout_episode_id is not null")
    pe_by_bzid = {str(r["buzzsprout_episode_id"]): int(r["id"]) for r in pe}
    print(f"Neon podcast_episode: {len(pe_by_bzid)} rows with a Buzzsprout id (for FK linking)")

    rows, no_guid, linked = [], 0, 0
    for rec in records:
        r = build_row(rec, pe_by_bzid)
        if not r["guid"]:
            no_guid += 1
            continue
        if r["podcast_episode_id"] is not None:
            linked += 1
        rows.append(r)
    print(f"Prepared {len(rows)} rows ({linked} FK-linked to a hub episode, "
          f"{no_guid} skipped for missing GUID)")

    placeholders = ", ".join(f"${i + 1}" for i in range(len(COLS)))
    updates = ", ".join(f"{c} = excluded.{c}" for c in COLS if c != "guid")
    upsert = (f"insert into buzzsprout_episode_data ({', '.join(COLS)}) "
              f"values ({placeholders}) "
              f"on conflict (guid) do update set {updates}, updated_at = now()")

    if not apply:
        print("\nDRY-RUN — no writes. Sample of first 3 prepared rows:")
        for r in rows[:3]:
            print(f"  EP {r['episode_number']}  guid={r['guid']}  bz={r['buzzsprout_episode_id']}"
                  f"  pe_id={r['podcast_episode_id']}  {str(r['title'])[:48]}")
        print("\nRe-run with --apply to write.")
        return

    for r in rows:
        neon_sql(dsn, upsert, [r[c] for c in COLS])
    total = neon_sql(dsn, "select count(*)::int as n from buzzsprout_episode_data")[0]["n"]
    print(f"\nAPPLIED: upserted {len(rows)} rows. buzzsprout_episode_data now holds {total} rows.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"SEED FAILED: {e}", file=sys.stderr)
        raise
