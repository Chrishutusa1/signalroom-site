#!/usr/bin/env python3
"""Insert the AI Health Pulse signup block above the footer on every page.

Dry-run by default (this repo's convention for mutating scripts). Pass --apply
to write. Idempotent: pages that already carry the SR-NEWSLETTER-SIGNUP marker
are skipped. Also appends the signup styles to css/style.css once.

Stdlib only. Preserves each file's line endings (the site is mostly CRLF).

    python _add_newsletter_signup.py            # report only
    python _add_newsletter_signup.py --apply    # write changes
"""
import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MARKER = "SR-NEWSLETTER-SIGNUP"
CSS_MARKER = "/* SR-NEWSLETTER-SIGNUP styles */"
SKIP_DIRS = {"node_modules", ".git", ".claude", "tools", "tests", "netlify", "docs", "_worktrees", "app"}
SKIP_FILES = {"404.html", "privacy-policy.html"}

CSS = """
/* SR-NEWSLETTER-SIGNUP styles */
.newsletter-signup-section { background: var(--bg-alt, #f8f9fa); padding: var(--space-lg, 2.5rem) 0; }
.newsletter-signup-card { max-width: 760px; margin: 0 auto; text-align: center; padding: 2rem 1.5rem; background: #fff; border-radius: 12px; border-left: 4px solid #6C5CE7; box-shadow: 0 1px 3px rgba(26, 26, 46, 0.08); }
.newsletter-signup-card h2 { margin: 0.5rem 0 0.5rem; font-size: 1.5rem; }
.newsletter-signup-card p { margin: 0 0 1.1rem; color: #444; line-height: 1.6; }
.newsletter-signup__label { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; }
.newsletter-signup__row { display: flex; gap: 0.6rem; max-width: 480px; margin: 0 auto; }
.newsletter-signup__input { flex: 1 1 auto; min-width: 0; padding: 0.75rem 0.9rem; border: 1px solid #c9c9d6; border-radius: 8px; font: inherit; }
.newsletter-signup__input:focus-visible { outline: 2px solid #6C5CE7; outline-offset: 2px; }
.newsletter-signup__hp { position: absolute; left: -9999px; width: 1px; height: 1px; opacity: 0; }
.newsletter-signup__button { flex: 0 0 auto; }
.newsletter-signup__button:disabled { opacity: 0.6; cursor: wait; }
.newsletter-signup__status { min-height: 1.4em; margin: 0.6rem 0 0; font-size: 0.95rem; color: #444; }
.newsletter-signup__status--ok { color: #1a1a2e; font-weight: 600; }
.newsletter-signup__status a { color: #6C5CE7; text-decoration: underline; }
.newsletter-signup__fine { margin: 0.75rem 0 0; font-size: 0.85rem; color: #666; }
@media (max-width: 480px) { .newsletter-signup__row { flex-direction: column; } }
"""


def campaign_for(rel: str) -> str:
    rel = rel.replace("\\", "/")
    if rel == "index.html":
        return "homepage"
    if rel.startswith("episodes/"):
        return "episode"
    if rel.lower().startswith("articles/"):
        return "article"
    if rel.startswith("topics/"):
        return "topic"
    return "footer"


def block(campaign: str, nl: str) -> str:
    html = f"""  <!-- {MARKER} -->
  <section class="newsletter-signup-section" aria-labelledby="newsletter-signup-title">
    <div class="container">
      <div class="newsletter-signup-card">
        <span class="section-label">The AI Health Pulse</span>
        <h2 id="newsletter-signup-title">Get the weekly healthcare AI newsletter</h2>
        <p>Weekly newsletter for healthcare executives on AI strategy, regulation, and operational reality.</p>
        <form class="newsletter-signup" data-newsletter-signup data-campaign="{campaign}" novalidate>
          <label class="newsletter-signup__label" for="newsletter-email">Email address</label>
          <div class="newsletter-signup__row">
            <input id="newsletter-email" class="newsletter-signup__input" type="email" name="email" placeholder="you@organization.com" autocomplete="email" required>
            <input class="newsletter-signup__hp" type="text" name="company" tabindex="-1" autocomplete="off" aria-hidden="true">
            <button class="btn btn-primary newsletter-signup__button" type="submit">Subscribe</button>
          </div>
          <p class="newsletter-signup__status" data-newsletter-status role="status" aria-live="polite"></p>
          <noscript><p class="newsletter-signup__fine"><a href="https://aihealthpulse.beehiiv.com/subscribe?utm_source=signalroompodcast.com&amp;utm_medium=site-form-fallback" target="_blank" rel="noopener">Subscribe on the newsletter page</a></p></noscript>
        </form>
        <p class="newsletter-signup__fine">Free. Unsubscribe any time.</p>
      </div>
    </div>
  </section>
  <script src="/js/newsletter-signup.js" defer></script>
"""
    return html.replace("\n", nl)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    footer_re = re.compile(r"(?m)^[ \t]*<footer\b")
    changed, skipped_marker, no_footer = [], [], []
    for path in sorted(ROOT.rglob("*.html")):
        rel = path.relative_to(ROOT)
        if any(part in SKIP_DIRS for part in rel.parts) or str(rel) in SKIP_FILES:
            continue
        raw = path.read_bytes()
        text = raw.decode("utf-8")
        if MARKER in text:
            skipped_marker.append(str(rel))
            continue
        m = footer_re.search(text)
        if not m:
            no_footer.append(str(rel))
            continue
        nl = "\r\n" if "\r\n" in text else "\n"
        new = text[: m.start()] + block(campaign_for(str(rel)), nl) + nl + text[m.start():]
        changed.append(str(rel))
        if args.apply:
            path.write_bytes(new.encode("utf-8"))

    css_path = ROOT / "css" / "style.css"
    css_text = css_path.read_text(encoding="utf-8")
    css_needed = CSS_MARKER not in css_text
    if css_needed and args.apply:
        nl = "\r\n" if "\r\n" in css_text else "\n"
        css_path.write_bytes((css_text.rstrip("\r\n") + nl + CSS.replace("\n", nl)).encode("utf-8"))

    mode = "APPLIED" if args.apply else "DRY RUN"
    print(f"[{mode}] pages to change: {len(changed)}; already done: {len(skipped_marker)}; no <footer>: {len(no_footer)}; css append needed: {css_needed}")
    for rel in no_footer:
        print("  no footer:", rel)
    if not args.apply:
        print("  (re-run with --apply to write)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
