#!/usr/bin/env python3
"""Generate sitemap.xml from the HTML files on disk (GAPS.md #8).

The sitemap was fully manual — three chances to forget per new page
(canonical, _redirects, sitemap). This script makes the sitemap derived:

  URL rules (verified against the live sitemap 2026-07-12, zero drift):
    index.html            -> https://signalroompodcast.com/
    <page>.html           -> /<page>            (extensionless, apex host)
    episodes/<slug>.html  -> /episodes/<slug>
    topics/<slug>.html    -> /topics/<slug>
    Articles/index.html   -> /articles/         (trailing slash — matches its canonical)
    Articles/<slug>.html  -> /articles/<slug>   (lowercase URL, capital-A dir on disk)
    404.html              -> excluded

  <lastmod> policy: entries already in sitemap.xml KEEP their current
  lastmod (a regeneration must never mass-bump lastmod — that tells
  crawlers everything changed). New pages get the file's last git commit
  date. Hand-edit a lastmod after a real content update, or pass
  --touch <url> to reset it to the file's git date.

  <changefreq>/<priority> come from PAGE_META (curated root pages) and
  SECTION_DEFAULTS below — the script, not the XML, is the source of truth.

  Video tags: episode entries also carry Google's <video:video> extension
  (one sitemap, no separate video-sitemap.xml). Per episode the block is, in
  order of preference: (1) the block already in sitemap.xml (kept verbatim,
  like lastmod), (2) the block in a legacy video-sitemap.xml if one still
  exists (one-time migration), (3) built from the episode page's own
  VideoObject JSON-LD (this is what a NEW episode gets). To fix a wrong video
  title/description, edit that <video:video> block in sitemap.xml (or delete
  the block and regenerate to rebuild it from the page).

Usage:
  python _generate_sitemap.py            # dry-run: show what would change
  python _generate_sitemap.py --apply    # write sitemap.xml
  python _generate_sitemap.py --check    # exit 1 if sitemap.xml is stale (CI)
  python _generate_sitemap.py --touch https://signalroompodcast.com/faq --apply

Standard library only, like every script in this repo.
"""
import argparse
import datetime
import html
import json
import re
import subprocess
import sys
from pathlib import Path

SITE = "https://signalroompodcast.com"
ROOT = Path(__file__).resolve().parent
SITEMAP = ROOT / "sitemap.xml"
LEGACY_VIDEO_SITEMAP = ROOT / "video-sitemap.xml"  # retired; read once for migration
VIDEO_NS = "http://www.google.com/schemas/sitemap-video/1.1"
VIDEO_TAGS = ("thumbnail_loc", "title", "description", "player_loc",
              "duration", "publication_date", "family_friendly")
EXCLUDE = {"404.html"}

# Curated changefreq/priority for root pages. A new root page not listed
# here gets NEW_ROOT_DEFAULT and a loud note to curate it.
PAGE_META = {
    "guest-authors":                        ("monthly", "0.6"),
    "":                                     ("weekly", "1.0"),
    "about":                                ("monthly", "0.7"),
    "be-a-guest":                           ("monthly", "0.6"),
    "best-healthcare-ai-podcast":           ("monthly", "0.8"),
    "clinical-ai-patient-care-podcast":     ("monthly", "0.8"),
    "episodes":                             ("weekly", "0.9"),
    "faq":                                  ("monthly", "0.3"),
    "generative-ai-healthcare-podcast":     ("monthly", "0.8"),
    "guests":                               ("weekly", "0.9"),
    "notable-healthcare-ai-podcast-guests": ("monthly", "0.8"),
    "podcasts-like-nejm-ai-grand-rounds":   ("monthly", "0.8"),
    "privacy-policy":                       ("monthly", "0.3"),
    "responsible-ai-in-medicine":           ("monthly", "0.8"),
}
SECTION_DEFAULTS = {
    "episodes":     ("weekly", "0.8"),
    "watch":        ("weekly", "0.8"),
    "topics":       ("monthly", "0.7"),
    "articles":     ("monthly", "0.7"),
    "articles-hub": ("monthly", "0.6"),
}
NEW_ROOT_DEFAULT = ("monthly", "0.8")


def url_for(rel):
    """Map a repo-relative HTML path to its canonical URL (None = excluded)."""
    s = rel.replace("\\", "/")
    if s in EXCLUDE:
        return None
    if s == "index.html":
        return SITE + "/"
    if s.startswith("Articles/"):
        slug = s[len("Articles/"):-len(".html")]
        return SITE + "/articles/" if slug == "index" else SITE + "/articles/" + slug
    return SITE + "/" + s[:-len(".html")]


def meta_for(url, notes):
    path = url[len(SITE):].strip("/")
    if path == "articles":
        return SECTION_DEFAULTS["articles-hub"]
    section = path.split("/")[0] if "/" in path else None
    if section in SECTION_DEFAULTS:
        return SECTION_DEFAULTS[section]
    if path in PAGE_META:
        return PAGE_META[path]
    notes.append("NEW root page %s not in PAGE_META - using default %s/%s; "
                 "curate it in _generate_sitemap.py" % (url, *NEW_ROOT_DEFAULT))
    return NEW_ROOT_DEFAULT


def git_lastmod(rel):
    """Last commit date (YYYY-MM-DD) for a file; today if untracked."""
    try:
        out = subprocess.run(
            ["git", "log", "-1", "--format=%cs", "--", rel],
            cwd=ROOT, capture_output=True, text=True, check=True,
        ).stdout.strip()
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", out):
            return out
    except (subprocess.CalledProcessError, OSError):
        pass
    return datetime.date.today().isoformat()


def discover():
    pages = []
    for pattern in ("*.html", "episodes/*.html", "watch/*.html", "topics/*.html", "Articles/*.html"):
        for p in sorted(ROOT.glob(pattern)):
            rel = p.relative_to(ROOT).as_posix()
            url = url_for(rel)
            if url:
                pages.append((url, rel))
    return dict(pages)


def parse_video_block(text):
    """Return {tag: raw inner text} for the first <video:video> in text, or None."""
    m = re.search(r"<video:video>(.*?)</video:video>", text, re.S)
    if not m:
        return None
    block = {}
    for tag in VIDEO_TAGS:
        t = re.search(r"<video:%s>(.*?)</video:%s>" % (tag, tag), m.group(1), re.S)
        if t:
            block[tag] = t.group(1)
    return block or None


def existing_entries():
    if not SITEMAP.exists():
        return {}
    text = SITEMAP.read_text(encoding="utf-8")
    entries = {}
    for m in re.finditer(r"<url>(.*?)</url>", text, re.S):
        body = m.group(1)
        loc = re.search(r"<loc>(.*?)</loc>", body, re.S)
        lastmod = re.search(r"<lastmod>(.*?)</lastmod>", body, re.S)
        if loc and lastmod:
            entries[loc.group(1)] = {"lastmod": lastmod.group(1),
                                     "video": parse_video_block(body)}
    return entries


def legacy_video_entries():
    """Video blocks from the retired video-sitemap.xml (empty once it is deleted)."""
    if not LEGACY_VIDEO_SITEMAP.exists():
        return {}
    text = LEGACY_VIDEO_SITEMAP.read_text(encoding="utf-8")
    out = {}
    for m in re.finditer(r"<url>(.*?)</url>", text, re.S):
        loc = re.search(r"<loc>(.*?)</loc>", m.group(1), re.S)
        block = parse_video_block(m.group(1))
        if loc and block:
            out[loc.group(1)] = block
    return out


def iso_duration_seconds(value):
    m = re.fullmatch(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+(?:\.\d+)?)S)?", value or "")
    if not m or not any(m.groups()):
        return None
    h, mi, sec = m.groups()
    return str(int(h or 0) * 3600 + int(mi or 0) * 60 + int(float(sec or 0)))


def video_from_page(rel):
    """Build a video block from the page's own VideoObject JSON-LD (None if absent/incomplete)."""
    try:
        text = (ROOT / rel).read_text(encoding="utf-8")
    except OSError:
        return None

    def walk(o):
        if isinstance(o, dict):
            if o.get("@type") == "VideoObject":
                yield o
            for v in o.values():
                yield from walk(v)
        elif isinstance(o, list):
            for v in o:
                yield from walk(v)

    vo = None
    for raw in re.findall(r'<script type="application/ld\+json">(.*?)</script>', text, re.S):
        try:
            for node in walk(json.loads(raw)):
                vo = node
        except ValueError:
            continue
    if not vo:
        return None
    thumb = vo.get("thumbnailUrl")
    thumb = thumb[0] if isinstance(thumb, list) else thumb
    esc = lambda v: html.escape(str(v).strip(), quote=False)
    block = {
        "thumbnail_loc": thumb,
        "title": vo.get("name"),
        "description": vo.get("description"),
        "player_loc": vo.get("embedUrl") or vo.get("contentUrl"),
        "duration": iso_duration_seconds(vo.get("duration")),
        "publication_date": vo.get("uploadDate"),
        "family_friendly": "no" if vo.get("isFamilyFriendly") is False else "yes",
    }
    required = ("thumbnail_loc", "title", "description", "player_loc")
    if any(not block[k] for k in required):
        return None
    return {k: esc(v) for k, v in block.items() if v}


def sort_key(url):
    """Canonical order: home, root pages A-Z, episodes, topics, articles hub, articles."""
    path = url[len(SITE):].strip("/")
    if path == "":
        return (0, "")
    if path.startswith("episodes/"):
        return (2, path)
    if path.startswith("watch/"):
        return (3, path)
    if path.startswith("topics/"):
        return (4, path)
    if path == "articles":
        return (5, "")
    if path.startswith("articles/"):
        return (6, path)
    return (1, path)


def render(rows, newline):
    has_video = any(r[4] for r in rows)
    ns = ' xmlns:video="%s"' % VIDEO_NS if has_video else ""
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"%s>' % ns]
    for url, lastmod, changefreq, priority, video in rows:
        lines += ["  <url>",
                  "    <loc>%s</loc>" % url,
                  "    <lastmod>%s</lastmod>" % lastmod,
                  "    <changefreq>%s</changefreq>" % changefreq,
                  "    <priority>%s</priority>" % priority]
        if video:
            lines.append("    <video:video>")
            for tag in VIDEO_TAGS:
                if tag in video:
                    lines.append("      <video:%s>%s</video:%s>" % (tag, video[tag], tag))
            lines.append("    </video:video>")
        lines.append("  </url>")
    lines.append("</urlset>")
    return newline.join(lines) + newline


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true", help="write sitemap.xml")
    mode.add_argument("--check", action="store_true",
                      help="exit 1 if sitemap.xml differs from generated (CI)")
    ap.add_argument("--touch", action="append", default=[], metavar="URL",
                    help="reset this URL's lastmod to its file's git date")
    args = ap.parse_args()

    pages = discover()
    existing = existing_entries()
    legacy = legacy_video_entries()
    notes = []

    rows = []
    for url in sorted(pages, key=sort_key):
        changefreq, priority = meta_for(url, notes)
        if url in existing and url not in args.touch:
            lastmod = existing[url]["lastmod"]
        else:
            lastmod = git_lastmod(pages[url])
        video = None
        if "/episodes/" in url:
            video = ((existing.get(url) or {}).get("video")
                     or legacy.get(url)
                     or video_from_page(pages[url]))
            if not video:
                notes.append("episode %s has no video block and no usable VideoObject - "
                             "it will have no <video:video> entry" % url)
        rows.append((url, lastmod, changefreq, priority, video))

    for bad in set(args.touch) - set(pages):
        notes.append("--touch %s matches no page on disk - ignored" % bad)

    added = sorted(set(pages) - set(existing))
    removed = sorted(set(existing) - set(pages))

    raw = SITEMAP.read_bytes() if SITEMAP.exists() else b""
    newline = "\r\n" if b"\r\n" in raw else "\n"
    generated = render(rows, newline)
    current = raw.decode("utf-8") if raw else ""
    changed = generated != current

    label = "APPLY" if args.apply else ("CHECK" if args.check else "DRY-RUN")
    print("[sitemap] %s - %d pages on disk, %d entries in sitemap.xml"
          % (label, len(pages), len(existing)))
    for u in added:
        print("  + add    %s" % u)
    for u in removed:
        print("  - remove %s  (file gone - if the URL ever had links, add a 301 in _redirects)" % u)
    for n in notes:
        print("  ! %s" % n)

    if not changed:
        print("  sitemap.xml is up to date")
        return 0
    if args.check:
        print("  STALE: sitemap.xml does not match the files on disk - "
              "run: python _generate_sitemap.py --apply")
        return 1
    if args.apply:
        SITEMAP.write_bytes(generated.encode("utf-8"))
        print("  wrote sitemap.xml (%d entries)" % len(rows))
        return 0
    print("  would rewrite sitemap.xml (%d entries) - rerun with --apply" % len(rows))
    return 0


if __name__ == "__main__":
    sys.exit(main())
