#!/usr/bin/env python3
"""Site-wide <title> / <meta name="description"> publish gate (stdlib-only).

    python _validate_meta.py             # gate every page on the site
    python _validate_meta.py a.html ...  # gate only the named files

_validate_episode.py gates episodes/*.html (length limits plus the shorts-alt
rule). This gates the same two length limits across EVERY page, which is where
the over-length titles and descriptions actually accumulated: the episode loop
never looked at root pages, topics/, watch/ or Articles/, so 13 violations sat
live on production undetected.

Length is measured the way a search engine sees the rendered page, so HTML
entities count as the single character they render as (&amp; is 1, not 5).

app/ is excluded: the Property Manager tool is noindex and deliberately outside
the sitemap and _redirects, so the new-page checklist does not apply to it.
"""
import re
import sys
from html import unescape
from pathlib import Path

TITLE_MAX = 57
META_MAX = 155
EXCLUDE_DIRS = {".git", "node_modules", "app"}

TITLE_RE = re.compile(r"<title>(.*?)</title>", re.S)
DESC_RE = re.compile(r'<meta\s+name="description"\s+content="(.*?)"', re.S)


def rendered_len(text):
    return len(unescape(text).strip())


def check(path):
    """Return a list of failure strings for one file."""
    src = path.read_text(encoding="utf-8", errors="replace")
    fails = []
    m = TITLE_RE.search(src)
    if m and rendered_len(m.group(1)) > TITLE_MAX:
        fails.append(f"<title> is {rendered_len(m.group(1))} chars (max {TITLE_MAX}): "
                     f"{unescape(m.group(1)).strip()}")
    m = DESC_RE.search(src)
    if m and rendered_len(m.group(1)) > META_MAX:
        fails.append(f'<meta name="description"> is {rendered_len(m.group(1))} chars '
                     f"(max {META_MAX}): {unescape(m.group(1)).strip()}")
    return fails


def site_pages():
    for p in sorted(Path(".").rglob("*.html")):
        if EXCLUDE_DIRS.isdisjoint(p.parts):
            yield p


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    paths = [Path(a) for a in args] if args else list(site_pages())
    bad = 0
    for p in paths:
        for f in check(p):
            print(f"FAIL {p}: {f}")
            bad += 1
    if bad:
        print(f"\n{bad} publish-gate violation(s) across {len(paths)} page(s)")
        return 1
    print(f"PASS - {len(paths)} page(s), all titles <={TITLE_MAX} and "
          f"descriptions <={META_MAX}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
