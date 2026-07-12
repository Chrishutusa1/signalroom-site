"""
signalroom-publish-normalize — defense-in-depth guard for the episode publish flow.

Why this exists
---------------
The shorts/clips carousel on every episode page is NOT rendered by any
version-controlled local script. `podcast_stats_capture/capture.py` only writes
shorts DATA to Airtable (table tblan7fxvxW0kpti2); `SignalRoom/build_episodes.py`
builds the main episode page but not the carousel. The carousel HTML is injected
by the MANUAL claude.ai "add-podcast-episode" routine, whose template historically
emits two recurring Ahrefs defects on every new episode:

  1. Empty alt on each shorts thumbnail:
       <a class="episode-shorts-item ..." ... data-short-title="TITLE">
         <img src=".../mqdefault.jpg" alt="" loading="lazy"><span>TITLE</span></a>
     -> should be alt="TITLE" (the clip's data-short-title).

  2. New episode URLs are never pushed to IndexNow (Bing/Yandex), so they sit
     undiscovered until the next crawl.

Because that routine lives in the cloud and can't be edited from the repo, this
script is the durable, idempotent guard that runs as part of the SR publish flow:

  --fix-alt   (default) fills any EMPTY shorts-thumbnail alt from its sibling
              data-short-title, across episodes/*.html. Idempotent: only ever
              touches alt="" — a filled alt is left exactly as-is.

  --indexnow  POSTs URLs to https://api.indexnow.org/IndexNow using the key file
              already live at the domain root
              (https://signalroompodcast.com/1577c9c65cc397ca183ed80f92e0f9cf.txt).

Note: the carousel is injected by a SEPARATE, later cloud pass (after the episode's
YouTube Shorts/clips are cut + captured to Airtable), not at episode creation. A
fresh episode has no carousel until then. So run this guard right after the
shorts-injection pass (and after add-podcast-episode, harmlessly — it's a no-op on
pages with no carousel or with alt already filled).

Publish sequence (manual netlify-drop prod deploy model — see signal-room-site skill):
  1. (cloud routine injects/updates the episode page's shorts carousel)
  2. python signalroom-publish-normalize.py --fix-alt --apply       # before deploy
  3. netlify deploy --prod --site=98c71b47-... --dir=.              # publish
  4. python signalroom-publish-normalize.py --indexnow --url <episode-url> --apply
                                                                    # after it's live

Dry-run by default (matches signalroom-airtable-bridge.py). Pass --apply to act.
Standard library only (no third-party deps) so it runs identically locally and in
the cloud routine.
"""

import argparse
import re
import sys
import json
import urllib.request
import urllib.error
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
EPISODES_DIR = REPO_ROOT / "episodes"
SITEMAP = REPO_ROOT / "sitemap.xml"

# IndexNow — key file is live at the domain root and committed to the repo.
INDEXNOW_ENDPOINT = "https://api.indexnow.org/IndexNow"
INDEXNOW_KEY = "1577c9c65cc397ca183ed80f92e0f9cf"
INDEXNOW_HOST = "signalroompodcast.com"
INDEXNOW_KEY_LOCATION = f"https://{INDEXNOW_HOST}/{INDEXNOW_KEY}.txt"
SITE_ORIGIN = f"https://{INDEXNOW_HOST}"
UA = "signalroom-publish-normalize/1.0"

# A single shorts-carousel anchor, captured whole so we only rewrite the img that
# belongs to it (the anchor carries the authoritative data-short-title).
SHORTS_ITEM_RE = re.compile(
    r'<a\b[^>]*\bclass="[^"]*\bepisode-shorts-item\b[^"]*"[^>]*>.*?</a>',
    re.DOTALL,
)
DATA_SHORT_TITLE_RE = re.compile(r'\bdata-short-title="([^"]*)"')


# ---- alt normalizer --------------------------------------------------------

def fix_alt_in_html(html):
    """Return (new_html, num_fixed). Fills empty shorts-thumbnail alt= from the
    anchor's data-short-title. Only ever rewrites alt="" — idempotent."""
    fixed = 0

    def fix_anchor(m):
        nonlocal fixed
        block = m.group(0)
        tm = DATA_SHORT_TITLE_RE.search(block)
        if not tm:
            return block
        title = tm.group(1)  # already HTML-escaped in the attribute context
        if not title:
            return block
        # Only fill an EMPTY alt; leave any already-filled alt untouched.
        new_block, n = re.subn(r'\balt=""', f'alt="{title}"', block, count=1)
        fixed += n
        return new_block

    new_html = SHORTS_ITEM_RE.sub(fix_anchor, html)
    return new_html, fixed


def run_fix_alt(apply):
    if not EPISODES_DIR.is_dir():
        print(f"ERROR: episodes dir not found at {EPISODES_DIR}", file=sys.stderr)
        return 1, []
    total_fixed = 0
    changed_files = []
    for page in sorted(EPISODES_DIR.glob("*.html")):
        html = page.read_text(encoding="utf-8")
        new_html, n = fix_alt_in_html(html)
        if n:
            total_fixed += n
            changed_files.append(page)
            print(f"  {'FIX ' if apply else 'WOULD FIX '}{n:>2} empty alt  {page.name}")
            if apply:
                page.write_text(new_html, encoding="utf-8")
    if total_fixed == 0:
        print("  all shorts thumbnails already have non-empty alt - nothing to do")
    else:
        verb = "filled" if apply else "would fill"
        print(f"  {verb} {total_fixed} empty alt(s) across {len(changed_files)} file(s)")
    return 0, changed_files


# ---- IndexNow --------------------------------------------------------------

def sitemap_urls():
    if not SITEMAP.is_file():
        return []
    text = SITEMAP.read_text(encoding="utf-8")
    return re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", text)


def episode_url_for(page_path):
    """Canonical extensionless episode URL for an episodes/*.html file."""
    return f"{SITE_ORIGIN}/episodes/{page_path.stem}"


def submit_indexnow(urls, apply):
    urls = [u for u in dict.fromkeys(urls) if u.startswith(SITE_ORIGIN)]
    if not urls:
        print("  no in-domain URLs to submit", file=sys.stderr)
        return 1
    payload = {
        "host": INDEXNOW_HOST,
        "key": INDEXNOW_KEY,
        "keyLocation": INDEXNOW_KEY_LOCATION,
        "urlList": urls,
    }
    print(f"  IndexNow: {len(urls)} URL(s) -> {INDEXNOW_ENDPOINT}")
    for u in urls:
        print(f"    {u}")
    if not apply:
        print("  (dry-run - pass --apply to actually submit)")
        return 0
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        INDEXNOW_ENDPOINT,
        data=data,
        method="POST",
        headers={"Content-Type": "application/json; charset=utf-8", "User-Agent": UA},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            code = resp.getcode()
            body = resp.read().decode("utf-8", "replace").strip()
    except urllib.error.HTTPError as e:
        code = e.code
        body = e.read().decode("utf-8", "replace").strip()
    print(f"  IndexNow HTTP {code}{(' - ' + body) if body else ''}")
    # 200 = accepted, 202 = accepted/pending validation. Anything else is a failure.
    return 0 if code in (200, 202) else 1


# ---- CLI -------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fix-alt", action="store_true",
                    help="fill empty shorts-thumbnail alt from data-short-title (default action)")
    ap.add_argument("--indexnow", action="store_true",
                    help="submit URLs to IndexNow")
    ap.add_argument("--url", action="append", default=[], metavar="URL",
                    help="explicit URL to submit to IndexNow (repeatable)")
    ap.add_argument("--all", action="store_true",
                    help="with --indexnow: submit every URL in sitemap.xml")
    ap.add_argument("--apply", action="store_true",
                    help="actually write files / POST to IndexNow (default: dry-run)")
    args = ap.parse_args()

    # Default to the alt fix when no explicit action is chosen.
    do_fix = args.fix_alt or not (args.fix_alt or args.indexnow)

    rc = 0
    changed_files = []
    if do_fix:
        print(f"[fix-alt] {'APPLY' if args.apply else 'DRY-RUN'}")
        rc_fix, changed_files = run_fix_alt(args.apply)
        rc |= rc_fix

    if args.indexnow:
        print(f"[indexnow] {'APPLY' if args.apply else 'DRY-RUN'}")
        urls = list(args.url)
        if args.all:
            urls += sitemap_urls()
        # If nothing was named but we just fixed pages, submit those episodes.
        if not urls and changed_files:
            urls += [episode_url_for(p) for p in changed_files]
        rc |= submit_indexnow(urls, args.apply)

    return rc


if __name__ == "__main__":
    sys.exit(main())
