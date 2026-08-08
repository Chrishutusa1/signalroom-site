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

Usage:
  python _generate_sitemap.py            # dry-run: show what would change
  python _generate_sitemap.py --apply    # write sitemap.xml
  python _generate_sitemap.py --check    # exit 1 if sitemap.xml is stale (CI)
  python _generate_sitemap.py --touch https://signalroompodcast.com/faq --apply

Standard library only, like every script in this repo.
"""
import argparse
import datetime
import re
import subprocess
import sys
from pathlib import Path

SITE = "https://signalroompodcast.com"
ROOT = Path(__file__).resolve().parent
SITEMAP = ROOT / "sitemap.xml"
EXCLUDE = {"404.html"}

# Curated changefreq/priority for root pages. A new root page not listed
# here gets NEW_ROOT_DEFAULT and a loud note to curate it.
PAGE_META = {
    "":                                     ("weekly", "1.0"),
    "about":                                ("monthly", "0.7"),
    "be-a-guest":                           ("monthly", "0.6"),
    "best-healthcare-ai-podcast":           ("monthly", "0.8"),
    "clinical-ai-patient-care-podcast":     ("monthly", "0.8"),
    "episodes":                             ("weekly", "0.9"),
    "faq":                                  ("monthly", "0.3"),
    "generative-ai-healthcare-podcast":     ("monthly", "0.8"),
    "guests":                               ("weekly", "0.9"),
    "newsletter":                           ("monthly", "0.5"),
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


def existing_entries():
    if not SITEMAP.exists():
        return {}
    text = SITEMAP.read_text(encoding="utf-8")
    entries = {}
    for m in re.finditer(
        r"<url>\s*<loc>(.*?)</loc>\s*<lastmod>(.*?)</lastmod>\s*"
        r"<changefreq>(.*?)</changefreq>\s*<priority>(.*?)</priority>\s*</url>",
        text, re.S,
    ):
        entries[m.group(1)] = {"lastmod": m.group(2)}
    return entries


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
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for url, lastmod, changefreq, priority in rows:
        lines += ["  <url>",
                  "    <loc>%s</loc>" % url,
                  "    <lastmod>%s</lastmod>" % lastmod,
                  "    <changefreq>%s</changefreq>" % changefreq,
                  "    <priority>%s</priority>" % priority,
                  "  </url>"]
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
    notes = []

    rows = []
    for url in sorted(pages, key=sort_key):
        changefreq, priority = meta_for(url, notes)
        if url in existing and url not in args.touch:
            lastmod = existing[url]["lastmod"]
        else:
            lastmod = git_lastmod(pages[url])
        rows.append((url, lastmod, changefreq, priority))

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
