"""
Bulk rollout of three mobile-perf edits across all HTML pages on the
Signal Room site. Mirrors the edits already made to index.html in
commits 93b702f and 80441ee.

Three edits per file:
1. Add a GTM preconnect <link> before the gtag script block.
2. Replace the sync/async gtag block (multiline OR minified) with a
   deferred loader that fires on requestIdleCallback or first user
   interaction, with a 3s setTimeout fallback. The dataLayer + gtag()
   shim still runs synchronously so no events are lost.
3. Replace the render-blocking Google Fonts <link rel="stylesheet">
   with a preload + onload swap and a <noscript> fallback.

Leaves dns-prefetch hints alone (harmless, redundant with preconnect).
Skips any file that already has the deferred loader (loadGA present).

Usage:
    python .claude/rollout_perf_edits.py           # dry run, report only
    python .claude/rollout_perf_edits.py --apply   # write changes
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APPLY = "--apply" in sys.argv

# --- GA block patterns ------------------------------------------------------

GA_BLOCK_MULTILINE = re.compile(
    r"""(?P<indent>[ \t]*)<script\s+async\s+src="https://www\.googletagmanager\.com/gtag/js\?id=G-RZNHLJSRW3"></script>\s*\n"""
    r"""[ \t]*<script>\s*\n"""
    r"""[ \t]*window\.dataLayer\s*=\s*window\.dataLayer\s*\|\|\s*\[\];?\s*\n"""
    r"""[ \t]*function\s+gtag\(\)\s*\{\s*dataLayer\.push\(arguments\);?\s*\}\s*\n"""
    r"""[ \t]*gtag\(\s*'js'\s*,\s*new\s+Date\(\)\s*\);?\s*\n"""
    r"""[ \t]*gtag\(\s*'config'\s*,\s*'G-RZNHLJSRW3'\s*\);?\s*\n"""
    r"""[ \t]*</script>"""
)

GA_BLOCK_MINIFIED = re.compile(
    r"""(?P<indent>[ \t]*)<script\s+async\s+src="https://www\.googletagmanager\.com/gtag/js\?id=G-RZNHLJSRW3"></script>\s*\n"""
    r"""[ \t]*<script>window\.dataLayer=window\.dataLayer\|\|\[\];function gtag\(\)\{dataLayer\.push\(arguments\)\}gtag\('js',new Date\(\)\);gtag\('config','G-RZNHLJSRW3'\);</script>"""
)

def ga_replacement(indent: str) -> str:
    inner = indent + "  "
    return (
        f'{indent}<link rel="preconnect" href="https://www.googletagmanager.com">\n'
        f'{indent}<script>\n'
        f'{inner}window.dataLayer = window.dataLayer || [];\n'
        f'{inner}function gtag(){{dataLayer.push(arguments);}}\n'
        f"{inner}gtag('js', new Date());\n"
        f"{inner}gtag('config', 'G-RZNHLJSRW3');\n"
        f'{inner}(function(){{\n'
        f'{inner}  var loaded = false;\n'
        f'{inner}  function loadGA(){{\n'
        f'{inner}    if (loaded) return; loaded = true;\n'
        f"{inner}    var s = document.createElement('script');\n"
        f'{inner}    s.async = true;\n'
        f"{inner}    s.src = 'https://www.googletagmanager.com/gtag/js?id=G-RZNHLJSRW3';\n"
        f'{inner}    document.head.appendChild(s);\n'
        f'{inner}  }}\n'
        f"{inner}  var events = ['scroll','click','touchstart','keydown','mousemove'];\n"
        f'{inner}  events.forEach(function(e){{ window.addEventListener(e, loadGA, {{passive:true, once:true}}); }});\n'
        f"{inner}  if ('requestIdleCallback' in window) {{ requestIdleCallback(loadGA, {{timeout: 4000}}); }}\n"
        f'{inner}  else {{ setTimeout(loadGA, 3000); }}\n'
        f'{inner}}})();\n'
        f'{indent}</script>'
    )

# --- Google Fonts pattern ---------------------------------------------------

FONT_URL = "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap"
FONT_LINK = re.compile(
    r"""(?P<indent>[ \t]*)<link\s+href="%s"\s+rel="stylesheet">""" % re.escape(FONT_URL)
)

def font_replacement(indent: str) -> str:
    return (
        f'{indent}<link rel="preload" as="style" href="{FONT_URL}" onload="this.onload=null;this.rel=\'stylesheet\'">\n'
        f'{indent}<noscript><link rel="stylesheet" href="{FONT_URL}"></noscript>'
    )

# --- Runner -----------------------------------------------------------------

def process(path: Path):
    text = path.read_text(encoding="utf-8")
    original = text
    report = []

    if "loadGA" in text:
        return "skip (already deferred)", False

    m = GA_BLOCK_MULTILINE.search(text)
    if m:
        text = text[:m.start()] + ga_replacement(m.group("indent")) + text[m.end():]
        report.append("GA multiline -> deferred")
    else:
        m = GA_BLOCK_MINIFIED.search(text)
        if m:
            text = text[:m.start()] + ga_replacement(m.group("indent")) + text[m.end():]
            report.append("GA minified -> deferred")
        else:
            return "MISS: no GA block matched", False

    fm = FONT_LINK.search(text)
    if fm:
        text = text[:fm.start()] + font_replacement(fm.group("indent")) + text[fm.end():]
        report.append("fonts -> preload+onload")
    else:
        report.append("fonts MISS (skipped)")

    if text != original:
        if APPLY:
            path.write_text(text, encoding="utf-8")
        return ", ".join(report), True
    return ", ".join(report), False


def main():
    html_files = sorted(
        p for p in ROOT.rglob("*.html")
        if ".git" not in p.parts and ".netlify" not in p.parts and ".claude" not in p.parts
    )
    changed = skipped = missed = 0
    for p in html_files:
        status, did_change = process(p)
        rel = p.relative_to(ROOT).as_posix()
        if status.startswith("skip"):
            print(f"  [SKIP] {rel}  ({status})")
            skipped += 1
        elif status.startswith("MISS"):
            print(f"  [MISS] {rel}  ({status})")
            missed += 1
        else:
            marker = "WRITE" if APPLY else "DRY  "
            print(f"  [{marker}] {rel}  ({status})")
            changed += 1
    print()
    print(f"Summary: changed={changed}, skipped={skipped}, missed={missed}, total={len(html_files)}")
    print(f"Mode: {'APPLIED' if APPLY else 'DRY RUN (pass --apply to write)'}")
    if missed:
        print("WARNING: one or more files had no recognizable GA block — review before apply.")
        sys.exit(1)


if __name__ == "__main__":
    main()
