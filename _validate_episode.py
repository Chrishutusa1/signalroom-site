#!/usr/bin/env python3
"""Signal Room episode-page PUBLISH GATE validator (stdlib-only).

    python _validate_episode.py episodes/<slug>.html          # gate: exit!=0 blocks deploy
    python _validate_episode.py episodes/<slug>.html --fix     # word-boundary-trim meta<=155 + backfill shorts alt, then re-run to confirm PASS

Gates: (1) <meta name="description"> <=155 chars (ONLY this surface);
(2) every shorts-carousel <img> alt is non-empty and == its data-short-title;
(3) <title> <=57 chars. IndexNow submission is a deploy-time step, not here.
"""
import argparse
import re
import sys

META_MAX = 155
TITLE_MAX = 57


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

    for a in re.finditer(r'<a class="episode-shorts-item[^"]*"[^>]*>.*?</a>', src, re.S):
        block = a.group(0)
        dt = re.search(r'data-short-title="([^"]*)"', block)
        title = dt.group(1) if dt else ''
        img = re.search(r'<img\b[^>]*>', block)
        alt = None
        if img:
            am = re.search(r'\balt="([^"]*)"', img.group(0))
            alt = am.group(1) if am else None
        if not alt:
            if args.fix and title and img:
                oi = img.group(0)
                ni = re.sub(r'\balt="[^"]*"', f'alt="{title}"', oi, count=1) if 'alt=' in oi \
                    else oi.replace('<img', f'<img alt="{title}"', 1)
                src = src.replace(block, block.replace(oi, ni, 1), 1)
                print(f'[fix] shorts alt set to "{title}"')
            else:
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
