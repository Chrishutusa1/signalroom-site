#!/usr/bin/env python3
"""Weekly lead-loss reconciliation: Netlify Forms vs Airtable.

WHY THIS EXISTS (2026-07-14): both submission-created.js functions deliberately
return HTTP 200 even when the Airtable write fails (anti-duplicate contract).
When the whole function invocation fails, the notification email AND auto-reply
fail with it, so a submission can exist ONLY in Netlify Forms with no one told.
Verified real losses before this script existed: Boris Berenberg (SR guest form,
2026-06-29) and Lisa Marceau (SR guest form, 2026-06-09) — 2 of 10 genuine
submissions, silently gone for 2-5 weeks.

WHAT IT DOES (read-only): pulls every submission for both forms via the Netlify
CLI, pulls the matching Airtable table, and reports any submission with no
Airtable record. Exit code is non-zero when anything unexplained is missing
(loud-failure repo convention). Nothing is ever written to Airtable or Netlify.

  python _reconcile_leads.py            # report; exit 1 if unexplained misses
  python _reconcile_leads.py --notify   # additionally email the report to Chris
                                        # via Resend (RESEND_API_KEY/AUTOREPLY_FROM)

INTENTIONAL absences (deleted spam, merged duplicates, pivoted applications)
belong in _reconcile_leads_resolved.json: {"<netlify submission id>": "reason"}.

Auth: needs an Airtable PAT with data.records:read on the base. Looked up in
order: env AIRTABLE_PAT -> `netlify api getEnvVars` on the SR site ->
C:/Users/PC/Desktop/HDSC/SignalRoom/.env / hdsc-site/.env (AIRTABLE_PAT= line).
Netlify CLI must be authed (it is on this machine; `netlify status` to check).
"""

import io
import json
import os
import re
import subprocess
import sys
import urllib.request

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

BASE_ID = "app3hF8k8ZGXvf9XF"  # Content Intelligence Hub
SR_SITE_ID = "98c71b47-cb1e-4eb2-8255-963349df8ccf"  # signalroompodcast.com

# form id -> (label, airtable table id)
FORMS = {
    "69c5456bd7d52d00088a50e8": ("SR guest-application", "tbloZMd3IzXNo20jY"),
    "6a10ad550c02dc000842a26f": ("HDSC lead-inquiry", "tbl8O3S6cYSeOxGHr"),
}

# Submissions that are tests/diagnostics, never expected in Airtable.
TEST_EMAILS = {"chris@hutchinsdatastrategy.com", "cjhutchins01@gmail.com",
               "pipeline-test@example.com"}
TEST_NAME_RE = re.compile(r"test|delete|loop-audit|live-proof|role-test|ui-test"
                          r"|autoreply|scorecard-path|diagnostic|verify", re.I)

RESOLVED_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "_reconcile_leads_resolved.json")

ENV_FALLBACK_FILES = [
    r"C:\Users\PC\Desktop\HDSC\SignalRoom\.env",
    r"C:\Users\PC\Desktop\HDSC\hdsc-site\.env",
]


def run_netlify(args):
    proc = subprocess.run(["netlify"] + args, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", shell=True)
    if proc.returncode != 0:
        raise SystemExit(f"netlify {' '.join(args)} failed:\n{proc.stderr[:2000]}")
    return json.loads(proc.stdout)


def airtable_pat():
    pat = os.environ.get("AIRTABLE_PAT")
    if pat:
        return pat
    try:
        for var in run_netlify(["api", "getEnvVars",
                                "--data", json.dumps({"site_id": SR_SITE_ID})]):
            if var.get("key") == "AIRTABLE_PAT":
                for v in var.get("values", []):
                    if v.get("value"):
                        return v["value"]
    except SystemExit as e:
        print(f"note: getEnvVars lookup failed ({e}); trying .env files", file=sys.stderr)
    for path in ENV_FALLBACK_FILES:
        try:
            with open(path, encoding="utf-8") as fh:
                for line in fh:
                    m = re.match(r"\s*AIRTABLE_PAT\s*=\s*(\S+)", line)
                    if m:
                        return m.group(1).strip().strip('"')
        except OSError:
            continue
    raise SystemExit("No AIRTABLE_PAT found (env var, Netlify env, or .env files). "
                     "Cannot reconcile without read access to Airtable.")


def site_env(key):
    """Resolve an env value the same way as airtable_pat(): process env first,
    then the SR site's Netlify env vars, then the local .env fallback files.
    Returns None if the key is not found anywhere."""
    val = os.environ.get(key)
    if val:
        return val
    try:
        for var in run_netlify(["api", "getEnvVars",
                                "--data", json.dumps({"site_id": SR_SITE_ID})]):
            if var.get("key") == key:
                for v in var.get("values", []):
                    if v.get("value"):
                        return v["value"]
    except SystemExit as e:
        print(f"note: getEnvVars lookup for {key} failed ({e}); trying .env files",
              file=sys.stderr)
    for path in ENV_FALLBACK_FILES:
        try:
            with open(path, encoding="utf-8") as fh:
                for line in fh:
                    m = re.match(rf"\s*{re.escape(key)}\s*=\s*(\S+)", line)
                    if m:
                        return m.group(1).strip().strip('"')
        except OSError:
            continue
    return None


def airtable_records(pat, table_id):
    records, offset = [], None
    while True:
        url = (f"https://api.airtable.com/v0/{BASE_ID}/{table_id}"
               f"?pageSize=100&fields%5B%5D=Name&fields%5B%5D=Email")
        if offset:
            url += f"&offset={offset}"
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {pat}"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            page = json.load(resp)
        records += page.get("records", [])
        offset = page.get("offset")
        if not offset:
            return records


def is_test(sub):
    email = (sub.get("email") or "").lower()
    name = sub.get("name") or ""
    return email in TEST_EMAILS or bool(TEST_NAME_RE.search(name))


def tokens(name):
    return {t.lower() for t in re.findall(r"[A-Za-z]{4,}", name or "")}


def matches(sub, records):
    """Email match, else 4+ char name-token overlap (catches publicist pivots
    like 'Ciara cbavis' -> 'Angel Mena ... via Ciara Bavis, Greenough Agency')."""
    email = (sub.get("email") or "").lower()
    sub_tokens = tokens(sub.get("name"))
    for r in records:
        f = r.get("fields", {})
        if email and (f.get("Email") or "").lower() == email:
            return r
        if sub_tokens and sub_tokens & tokens(f.get("Name")):
            return r
    return None


def main():
    notify = "--notify" in sys.argv
    try:
        with open(RESOLVED_PATH, encoding="utf-8") as fh:
            resolved = json.load(fh)
    except OSError:
        resolved = {}

    pat = airtable_pat()
    missing, lines = [], []
    for form_id, (label, table_id) in FORMS.items():
        subs = run_netlify(["api", "listFormSubmissions",
                            "--data", json.dumps({"form_id": form_id})])
        records = airtable_records(pat, table_id)
        for sub in subs:
            sid = sub.get("id", "")
            who = f"{sub.get('name')} <{sub.get('email')}> {sub.get('created_at', '')[:10]}"
            if is_test(sub):
                continue
            if sid in resolved:
                lines.append(f"  resolved   [{label}] {who} — {resolved[sid]}")
                continue
            if matches(sub, records):
                lines.append(f"  ok         [{label}] {who}")
            else:
                missing.append(f"  MISSING    [{label}] {who} (submission {sid})")
    report = "\n".join(missing + lines)
    print(f"Lead reconciliation — {len(missing)} unexplained missing\n{report}")

    if missing and notify:
        try:
            api_key = site_env("RESEND_API_KEY")
            sender = site_env("AUTOREPLY_FROM")
            if not api_key or not sender:
                print("notify SKIPPED: RESEND_API_KEY/AUTOREPLY_FROM not found — "
                      "no relay to send the reconciliation alert through.",
                      file=sys.stderr)
            else:
                to = [s.strip() for s
                      in (site_env("LEAD_NOTIFY_TO")
                          or "chris@hutchinsdatastrategy.com").split(",")
                      if s.strip()]
                payload = json.dumps({
                    "from": sender,
                    "to": to,
                    "subject": f"LEAD RECONCILIATION ALERT — {len(missing)} "
                               f"submission(s) missing from Airtable",
                    "text": f"{len(missing)} form submission(s) missing from "
                            f"Airtable:\n\n" + "\n".join(missing),
                }).encode()
                urllib.request.urlopen(urllib.request.Request(
                    "https://api.resend.com/emails", data=payload,
                    headers={"Authorization": f"Bearer {api_key}",
                             "Content-Type": "application/json"}),
                    timeout=30)
                print("notify: reconciliation alert emailed via Resend")
        except Exception as e:  # alert failure must not hide the exit code
            print(f"notify FAILED: {e}", file=sys.stderr)

    sys.exit(1 if missing else 0)


if __name__ == "__main__":
    main()
