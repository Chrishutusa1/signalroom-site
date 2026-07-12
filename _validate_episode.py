#!/usr/bin/env python3
"""Signal Room episode-page PUBLISH GATE validator (stdlib-only).

    python _validate_episode.py episodes/<slug>.html          # gate: exit!=0 blocks deploy
    python _validate_episode.py episodes/<slug>.html --fix     # word-boundary-trim meta<=155 + backfill shorts alt, then re-run to confirm PASS

Gates: (1) <meta name="description"> <=155 chars (ONLY this surface);
(2) every shorts-carousel <img> alt is non-empty and == its data-short-title;
(3) <title> <=57 chars. IndexNow submission is a deploy-time step, not here.

The shorts-alt FIX logic is NOT implemented here: signalroom-publish-normalize.py
is the authoritative alt implementation (it also runs in the cloud flow), and this
validator imports fix_alt_in_html/SHORTS_ITEM_RE from it (GAPS #6). This file only
gates; anything the normalize fixer can't cure (e.g. a missing alt attribute or an
empty data-short-title) stays a FAIL for a human to look at.
"""
import argparse
import importlib.util
import re
import sys
from pathlib import Path

# Failure messages quote page text (titles, alt text) that can carry
# non-cp1252 characters — keep prints from crashing on a Windows console.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

META_MAX = 155
TITLE_MAX = 57

# The one authoritative shorts-alt implementation lives in the normalize script
# (hyphenated filename, hence the spec loader).
_norm_spec = importlib.util.spec_from_file_location(
    "signalroom_publish_normalize",
    Path(__file__).resolve().parent / "signalroom-publish-normalize.py")
_normalize = importlib.util.module_from_spec(_norm_spec)
_norm_spec.loader.exec_module(_normalize)


def word_trim(text, limit):
    if len(text) <= limit:
        return text
    cut = text[:limit]
    if ' ' in cut:
        cut = cut[:cut.rfind(' ')]
    return cut.rstrip(' ,;:.-–—')


def main():
    ap = argparse.ArgumentParser(description="Signal Room episode publish-gate validator")
    ap.add_argument('path', help='path to episodes/<slug>.html')
    ap.add_argument('--fix', action='store_true',
                    help='auto-trim meta to <=155 at a word boundary and backfill shorts alt from data-short-title')
    args = ap.parse_args()

    with open(args.path, encoding='utf-8') as fh:
        src = fh.read()
    orig = src
    fails = []

    m = re.search(r'<title>(.*?)</title>', src, re.S)
    if not m:
        fails.append('no <title> found')
    elif len(m.group(1)) > TITLE_MAX:
        fails.append(f'title {len(m.group(1))} chars > {TITLE_MAX}: "{m.group(1)}"')

    m = re.search(r'(<meta\s+name="description"\s+content=")(.*?)("\s*/?>)', src)
    if not m:
        fails.append('no <meta name="description"> found')
    else:
        desc = m.group(2)
        if len(desc) > META_MAX:
            if args.fix:
                trimmed = word_trim(desc, META_MAX)
                src = src[:m.start(2)] + trimmed + src[m.end(2):]
                print(f'[fix] meta description {len(desc)} -> {len(trimmed)} chars')
            else:
                fails.append(f'meta description {len(desc)} chars > {META_MAX}: "{desc}"')

    if args.fix:
        src, n_alt = _normalize.fix_alt_in_html(src)
        if n_alt:
            print(f'[fix] filled {n_alt} empty shorts alt(s) via signalroom-publish-normalize')

    for a in _normalize.SHORTS_ITEM_RE.finditer(src):
        block = a.group(0)
        dt = _normalize.DATA_SHORT_TITLE_RE.search(block)
        title = dt.group(1) if dt else ''
        am = re.search(r'<img\b[^>]*\balt="([^"]*)"', block)
        if not (am and am.group(1)):
            fails.append(f'shorts-carousel thumbnail has empty/missing alt (should be "{title}")')

    if args.fix and src != orig:
        with open(args.path, 'w', encoding='utf-8') as fh:
            fh.write(src)

    if fails:
        print('FAIL - episode publish gates:')
        for f in fails:
            print('  - ' + f)
        sys.exit(1)
    print(f'PASS - meta<={META_MAX}, title<={TITLE_MAX}, shorts alt populated')


if __name__ == '__main__':
    main()
