#!/usr/bin/env python3
"""Verify that every cross-domain _redirects target is still a live canonical.

    python _check_external_redirects.py            # check all absolute targets
    python _check_external_redirects.py --verbose   # also print each response header set
    python _check_external_redirects.py --json      # machine-readable report

GAPS.md #13. Most _redirects rules point inside signalroompodcast.com, so CI can
verify them from the files on disk. A handful point at ANOTHER domain, and the
reason they are correct is a fact about that other site: /newsletter and
/newsletter.html 301 to https://hutchinsdatastrategy.com/the-ai-health-pulse
because HDSC's page declares itself the canonical AI Health Pulse entity (a
Periodical, with beehiiv/substack/LinkedIn only as sameAs).

Nothing in this repo can see that. The _redirects CI check validates line SHAPE
only, so if HDSC renames the page or moves its canonical, those rules keep
301ing to a URL that consolidates nothing, or to a 404, and the build stays
green. /newsletter carried 491 impressions and 32 AIHP-brand keywords when it
was retired, so the failure is silent and expensive.

Three things are checked per target:
  1. it answers 200 (not 404, not 5xx),
  2. it does not itself redirect (a hop here makes the real chain 2+ long),
  3. its rel="canonical" equals the URL we fetched, so the target is the
     consolidation point rather than a waypoint.

READ-ONLY. It fetches URLs and prints; it never writes a file, so unlike the
repo's mutating scripts there is no dry-run/--apply pair to remember.

DELIBERATELY NOT A CI GATE. Run it on demand and as part of the 30-day GSC
review. Wiring it into validate.yml would turn someone else's outage into a red
build here, and would produce confident false alarms: beehiiv already answers a
Cloudflare-style 403 to datacenter IPs while serving browsers and Googlebot a
200. GitHub runners are datacenter IPs. A check that cries wolf gets ignored,
and then it is worth less than nothing. For that reason a 403/429 is reported as
BLOCKED, not FAIL, and is retried once as Googlebot to show whether the origin
is discriminating by client rather than actually broken.

Exit codes are kept meaningful anyway, in case this is ever run from a wrapper:
  0  every target verified, or there was nothing to check
  1  at least one target is genuinely wrong (bad status, extra hop, canonical
     mismatch)
  2  at least one target could not be determined (network error, bot challenge)
     and nothing was found to be genuinely wrong

A cross-domain rule whose target is a Netlify template (`/insight/*` ->
`.../insight/:splat`) has no literal URL to fetch. Those are printed as SKIP and
do not affect the exit code, because failing every run on a deliberate template
is the kind of noise that gets a check ignored. They still need checking by hand,
which is why they are printed rather than dropped.

Standard library only, like every script in this repo.
"""
import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

REDIRECTS = Path(__file__).resolve().parent / "_redirects"

# This site's own hosts. A rule whose target is one of these is not cross-domain
# even when written as an absolute URL: the www->apex host rule at the top of
# _redirects is `https://www.signalroompodcast.com/*  https://signalroompodcast.com/:splat`,
# which is internal, and its target is a Netlify placeholder rather than a real URL.
OWN_HOSTS = {"signalroompodcast.com", "www.signalroompodcast.com"}

# Netlify rule placeholders (:splat, :id, and bare * ) mean the target is a
# template, not a URL, so there is nothing literal to fetch.
PLACEHOLDER_RE = re.compile(r"(?::[A-Za-z_]\w*|\*)")

UA = "signalroom-check-external-redirects/1.0 (+https://signalroompodcast.com)"
# Only sent as a second attempt on a 403/429, to tell "this origin blocks
# datacenter clients" apart from "this URL is broken". Search engines are the
# audience a 301 exists for, so what they are served is the answer that matters.
UA_GOOGLEBOT = ("Mozilla/5.0 (compatible; Googlebot/2.1; "
                "+http://www.google.com/bot.html)")
TIMEOUT = 30
CHALLENGE_CODES = {403, 429}
# Transport errors (TLS handshake timeout, connection reset) are retried once.
# Testing this against HDSC showed roughly 1 run in 4 failing the handshake
# through a proxied connection while the URL was perfectly healthy, and an ERROR
# on a good target is the same false alarm this script is written to avoid.
# A retry costs a second; a wrong verdict costs the check's credibility.
TRANSPORT_RETRIES = 1
RETRY_BACKOFF = 2.0

# A _redirects line is `pattern  target  status`. We want the ones whose TARGET
# is absolute, i.e. leaves this domain. Same shape the CI check enforces.
RULE_RE = re.compile(r"^(\S+)\s+(https?://\S+)\s+(\d{3}!?)\s*$")

CANONICAL_RE = re.compile(
    r'<link\b[^>]*\brel=["\']canonical["\'][^>]*>', re.I)
HREF_RE = re.compile(r'\bhref=["\']([^"\']+)["\']', re.I)


class NoRedirects(urllib.request.HTTPRedirectHandler):
    """Surface a 3xx as a result instead of quietly following it. A target that
    redirects is the whole point of check 2, so it must not be followed."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


OPENER = urllib.request.build_opener(NoRedirects)


def parse_targets(path):
    """Return (rules, skipped) for the cross-domain rules in _redirects.

    rules   [(lineno, pattern, target, status)] with a literal off-site target
    skipped [(lineno, target, why)] for absolute targets we cannot check, so a
            cross-domain rule is never dropped silently
    """
    rules, skipped = [], []
    for n, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        m = RULE_RE.match(line)
        if not m:
            continue
        pattern, target, status = m.group(1), m.group(2), m.group(3)
        host = urllib.parse.urlsplit(target).hostname or ""
        if host.lower() in OWN_HOSTS:
            continue                      # internal rule written absolutely
        if PLACEHOLDER_RE.search(urllib.parse.urlsplit(target).path or ""):
            skipped.append((n, target, "target is a Netlify template, not a literal URL"))
            continue
        rules.append((n, pattern, target, status))
    return rules, skipped


def fetch(url, ua):
    """Return (status, headers, body_text) without following redirects.

    Raises URLError/socket errors to the caller; a 3xx or 4xx comes back as a
    normal (status, headers, body) triple because those are findings, not
    failures of the check itself."""
    req = urllib.request.Request(url, headers={"User-Agent": ua})
    for attempt in range(TRANSPORT_RETRIES + 1):
        try:
            with OPENER.open(req, timeout=TIMEOUT) as resp:
                return resp.getcode(), dict(resp.headers), _read(resp)
        except urllib.error.HTTPError as e:
            # An HTTP status IS the answer, so never retry it: a 404 is a finding.
            return e.code, dict(e.headers or {}), _read(e)
        except Exception:                       # noqa: BLE001 - transport only
            if attempt == TRANSPORT_RETRIES:
                raise
            time.sleep(RETRY_BACKOFF)


def _read(resp):
    """Read at most enough bytes to contain a <head>. Some targets are large and
    the canonical is always near the top; 256 KiB is generous for a <head>."""
    return resp.read(262144).decode("utf-8", "replace")


def canonical_of(body):
    tag = CANONICAL_RE.search(body)
    if not tag:
        return None
    href = HREF_RE.search(tag.group(0))
    return href.group(1).strip() if href else None


def check_target(url):
    """Return a result dict for one URL. Never raises."""
    r = {"url": url, "verdict": None, "notes": []}
    try:
        status, headers, body = fetch(url, UA)
    except Exception as e:                      # noqa: BLE001 - report, never crash
        r["verdict"] = "ERROR"
        r["notes"].append(f"request failed: {type(e).__name__}: {e}")
        return r

    r["status"] = status

    if status in CHALLENGE_CODES:
        r["verdict"] = "BLOCKED"
        r["notes"].append(
            f"{status} to this client; a bot challenge, not necessarily a broken URL")
        try:
            bot_status, _, bot_body = fetch(url, UA_GOOGLEBOT)
        except Exception as e:                  # noqa: BLE001
            r["notes"].append(f"Googlebot retry also failed: {type(e).__name__}: {e}")
            return r
        r["googlebot_status"] = bot_status
        if bot_status == 200:
            r["notes"].append(
                "200 as Googlebot, so search engines can reach it and the 403 is "
                "this client's IP being filtered")
            canon = canonical_of(bot_body)
            r["canonical"] = canon
            if canon and canon.rstrip("/") != url.rstrip("/"):
                r["verdict"] = "FAIL"
                r["notes"].append(
                    f"canonical seen as Googlebot is {canon!r}, not the redirect target")
        else:
            r["notes"].append(f"{bot_status} as Googlebot too, so verify by hand")
        return r

    if 300 <= status < 400:
        r["verdict"] = "FAIL"
        loc = headers.get("Location") or headers.get("location") or "(no Location)"
        r["location"] = loc
        r["notes"].append(
            f"target itself {status}s to {loc}, making the real chain 2+ hops")
        return r

    if status != 200:
        r["verdict"] = "FAIL"
        r["notes"].append(f"target answers {status}, so the redirect lands nowhere useful")
        return r

    canon = canonical_of(body)
    r["canonical"] = canon
    if canon is None:
        r["verdict"] = "WARN"
        r["notes"].append(
            "200 but no rel=canonical, so the target does not declare itself the "
            "consolidation point")
        return r
    if canon.rstrip("/") != url.rstrip("/"):
        r["verdict"] = "FAIL"
        r["notes"].append(
            f"canonical is {canon!r}, not the redirect target, so this hop "
            "consolidates nothing")
        return r

    r["verdict"] = "PASS"
    r["notes"].append("200, no further hop, self-canonical")
    return r


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", action="store_true", help="emit the report as JSON")
    ap.add_argument("--verbose", "-v", action="store_true",
                    help="also print the rules each target came from")
    ap.add_argument("path", nargs="?", default=REDIRECTS, type=Path,
                    help="a _redirects file to read instead of this repo's")
    args = ap.parse_args()

    rules, skipped = parse_targets(args.path)
    if not rules:
        # Not the same thing as "all well": if the only cross-domain rule were
        # deleted, this script would have nothing to check and would otherwise
        # look like a clean pass. Say so out loud.
        msg = ("NOTE: no checkable cross-domain targets in _redirects. "
               "If you expected /newsletter here, the rule is gone, not healthy.")
        if skipped:
            msg += (f" {len(skipped)} cross-domain rule(s) were skipped as "
                    "templates and need checking by hand, listed below.")
        if args.json:
            print(json.dumps({"targets": 0, "note": msg, "skipped": skipped}, indent=2))
        else:
            print(msg)
            for lineno, target, why in skipped:
                print(f"SKIP    _redirects:{lineno} {target}\n        {why}")
        return 0

    # One rule per line, but several lines can share a target (/newsletter and
    # /newsletter.html both point at HDSC). Fetch each distinct URL once.
    sources = {}
    for lineno, pattern, target, status in rules:
        sources.setdefault(target, []).append(f"_redirects:{lineno} {pattern} ({status})")

    results = [check_target(u) for u in sources]

    if args.json:
        for r in results:
            r["sources"] = sources[r["url"]]
        print(json.dumps({"targets": len(results), "results": results,
                          "skipped": skipped}, indent=2))
    else:
        print(f"{len(results)} cross-domain target(s) in _redirects "
              f"across {len(rules)} rule(s)\n")
        for r in results:
            print(f"{r['verdict']:<8}{r['url']}")
            for note in r["notes"]:
                print(f"        {note}")
            if args.verbose:
                for s in sources[r["url"]]:
                    print(f"        from {s}")
            print()
        for lineno, target, why in skipped:
            print(f"SKIP    {target}\n        {why}\n        from _redirects:{lineno}\n")

    verdicts = [r["verdict"] for r in results]
    if "FAIL" in verdicts:
        return 1
    if "ERROR" in verdicts or "BLOCKED" in verdicts:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
