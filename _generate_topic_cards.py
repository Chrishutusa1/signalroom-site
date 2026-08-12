"""
_generate_topic_cards.py
Regenerates topic-page episode card sections from authoritative episode HTML data.

Authoritative source for ep_num, guest, yt_id: /episodes/*.html (JSON-LD + iframe embed)
Authoritative source for card_title, card_desc: this file (editorial curation)

Usage:
  python _generate_topic_cards.py           # dry-run: verify + print diff summary
  python _generate_topic_cards.py --apply   # write changes to topic HTML files

To add a new episode to a topic: add a dict entry to TOPICS below and re-run --apply.
To update guest name or YT ID: edit /episodes/{slug}.html and re-run --apply.
"""

from pathlib import Path
import re, sys

# Guest names carry non-cp1252 characters (e.g. "Atlı") — keep prints from
# crashing on a default Windows console.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO      = Path(__file__).resolve().parent
EP_DIR    = REPO / "episodes"
TOPIC_DIR = REPO / "topics"

# ── Authoritative episode index ───────────────────────────────────────────────
# Built from episode HTML files at runtime. Fields sourced:
#   ep_num  → JSON-LD "episodeNumber"
#   guest   → JSON-LD actor "@type"=Person "name"
#   yt_id   → first youtube.com/embed/{id} iframe src

def build_ep_index():
    index = {}
    skipped = []
    for f in sorted(EP_DIR.glob("*.html")):
        text = f.read_text(encoding="utf-8")
        ep_m    = re.search(r'"episodeNumber":\s*(\d+)', text)
        guest_m = re.search(r'"@type":\s*"Person"[^}]*?"name":\s*"([^"]+)"', text, re.DOTALL)
        yt_m    = re.search(r'youtube\.com/embed/([A-Za-z0-9_\-]+)', text)
        if not (ep_m and guest_m and yt_m):
            print(f"WARNING: incomplete JSON-LD/embed in {f.name} — skipping")
            skipped.append(f.name)
            continue
        index[f.stem] = {
            "ep":    int(ep_m.group(1)),
            "guest": guest_m.group(1),
            "yt_id": yt_m.group(1),
        }
    return index, skipped


# ── Per-topic card configs ────────────────────────────────────────────────────
# slug         = episode slug → looked up in ep_index for ep_num, guest, yt_id
# card_title   = short editorial title shown on card (not the full episode title)
# card_desc    = one-sentence editorial description on card
# guest_display = override the guest display name (use only when episode JSON-LD
#                 and the intended display name genuinely differ; fix the episode
#                 file when possible instead of using this override)

TOPICS = {

    "healthcare-ai-strategy": [
        dict(slug="data-readiness-ai-adoption",
             card_title="Data Readiness for AI Adoption",
             card_desc="Why most healthcare organizations aren't AI-ready, and what leaders must fix before scaling AI."),
        dict(slug="healthcare-ai-not-one-size-fits-all",
             card_title="Healthcare AI is Not One-Size-Fits-All",
             card_desc="Why healthcare organizations need customized AI strategies aligned with their unique operational realities."),
        dict(slug="ai-hype-to-real-value",
             card_title="From AI Hype to Real Value",
             card_desc="Moving past headlines and proof-of-concepts to define what matters: actual organizational benefit."),
        dict(slug="rethinking-healthcare-data-strategy",
             card_title="From AI Strategy to Execution",
             card_desc="Trust, leadership, and operational reality determine whether strategic ambitions become organizational reality."),
        dict(slug="enterprise-ai-journey-data-foundations",
             card_title="The Enterprise AI Journey",
             card_desc="Building enterprise AI capabilities from data foundations through generative and agentic AI applications."),
    ],

    "clinical-ai-patient-care": [
        dict(slug="dont-upload-medical-records-to-chatgpt",
             card_title="Don't Upload Your Medical Record to ChatGPT",
             card_desc="Why your full medical record should never go into a general AI chatbot, who's accountable when AI enters the exam room, and how to be a prepared patient.",
             guest_display="Dr. Terry Adirim"),
        dict(slug="patient-physician-journey-part-1",
             card_title="How AI Redefines the Patient-Physician Journey Part 1",
             card_desc="Exploring how AI reshapes the relationship between physicians, patients, and clinical decision-making."),
        dict(slug="patient-physician-journey-part-2",
             card_title="How AI Redefines the Patient-Physician Journey Part 2",
             card_desc="Continuing the conversation on physician-patient dynamics in an AI-augmented clinical environment."),
        dict(slug="ai-cant-replace-language-access",
             card_title="AI Can't Replace Language Access",
             card_desc="Why effective communication with limited English proficient patients requires humans, not algorithms."),
        dict(slug="healthcare-ai-complete-medical-records",
             card_title="Healthcare AI Fails Without Complete Medical Records",
             card_desc="The data completeness problem and its ripple effects on AI reliability and clinical trust."),
        dict(slug="balancing-human-judgment-clinical-trust",
             card_title="Balancing Human Judgment and Clinical Trust",
             card_desc="How to preserve physician autonomy and clinical judgment while leveraging AI recommendations."),
        dict(slug="ai-in-the-er-clinical-judgment",
             card_title="The Scary Truth About AI in the ER",
             card_desc="Emergency medicine demands rapid decisions with incomplete information. How AI fits into that reality."),
        dict(slug="caregivers-connective-tissue-healthcare",
             card_title="Caregivers as the Connective Tissue of Healthcare",
             card_desc="The human glue that holds clinical teams together and why caregiving cannot be automated away."),
    ],

    "healthcare-data-security": [
        dict(slug="ai-agents-patient-data-leak",
             card_title="When AI Agents Leak Patient Data",
             card_desc="How patient data reached a public AI prompt, why agents drift, and the governance layer needed to score, audit, and control them."),
        dict(slug="data-quality-ai-strategy",
             card_title="Data Quality and AI Strategy",
             card_desc="Why data quality forms the foundation of viable AI strategy and what it takes to improve it at scale."),
        dict(slug="authentic-intelligence-explainability",
             card_title="Authentic Intelligence: Explainability and Bias",
             card_desc="How to build AI systems that clinicians can understand and identify when bias is present."),
        dict(slug="ai-security-risks-cybersecurity",
             card_title="AI Security Risks",
             card_desc="Novel security threats introduced by AI systems and how healthcare organizations should prepare."),
        dict(slug="hidden-infrastructure-of-trust",
             card_title="The Hidden Infrastructure of Trust",
             card_desc="The unglamorous data and security infrastructure that makes trustworthy healthcare AI possible."),
        dict(slug="cybersecurity-ethical-leadership-ai",
             card_title="No Alerts, Still Breached",
             card_desc="Healthcare cybersecurity realities and why traditional monitoring may miss AI-specific threats."),
        dict(slug="ai-verification-drug-discovery-ep17",
             card_title="Why AI Verification is the Real Bottleneck",
             card_desc="How verification and validation slowdown healthcare AI deployment and why those constraints matter."),
    ],

    "ai-ethics-governance": [
        dict(slug="ai-agents-patient-data-leak",
             card_title="When AI Agents Leak Patient Data",
             card_desc="How patient data reached a public AI prompt, why agents drift, and the governance layer needed to score, audit, and control them."),
        dict(slug="human-ai-leadership-equation",
             card_title="Healthcare AI Leadership",
             card_desc="What leadership capabilities AI demands and why technical expertise alone cannot drive responsible AI deployment.",
             guest_display="Dr. Larry Kuhn"),   # episode JSON-LD says "Larry Kuhn"; page title says "Dr. Larry Kuhn"
        dict(slug="human-centered-ai-governance",
             card_title="AI Governance in Healthcare: Just Culture & Trauma-Informed Leadership",
             card_desc="Governance frameworks that preserve human agency, transparency, and the ability to refuse AI recommendations."),
        dict(slug="ai-ethics-ethical-leadership",
             card_title="AI Ethics and Ethical Leadership",
             card_desc="The difference between published principles and operational ethics. How leaders make ethical behavior structural."),
        dict(slug="healthcare-leadership-operational-reality",
             card_title="Healthcare Leadership, Operational Reality, and System Signals",
             card_desc="How governance decisions cascade through healthcare systems and shape organizational culture and outcomes."),
    ],

}


# ── Card HTML template ────────────────────────────────────────────────────────
LISTEN_ARROW = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M5 12h14M12 5l7 7-7 7"/></svg>'
PLAY_ICON    = '<svg viewBox="0 0 24 24"><polygon points="5,3 19,12 5,21"/></svg>'

def make_card(slug, ep, guest, yt_id, card_title, card_desc):
    return (
        f'        <a href="/episodes/{slug}" class="episode-card">\n'
        f'          <div class="episode-card-thumb">\n'
        f'            <img src="https://img.youtube.com/vi/{yt_id}/hqdefault.jpg" alt="{guest} episode" loading="lazy">\n'
        f'            <div class="episode-card-play">{PLAY_ICON}</div>\n'
        f'          </div>\n'
        f'          <div class="episode-card-body">\n'
        f'            <div class="episode-card-guest">{guest}</div>\n'
        f'            <div class="episode-card-title">{card_title}</div>\n'
        f'            <div class="episode-card-desc">{card_desc}</div>\n'
        f'          </div>\n'
        f'          <div class="episode-card-footer">\n'
        f'            <span class="episode-card-ep">Episode {ep}</span>\n'
        f'            <span class="episode-card-link">Listen Now {LISTEN_ARROW}</span>\n'
        f'          </div>\n'
        f'        </a>'
    )


# ── Section replacement ───────────────────────────────────────────────────────
# Anchors: <div class="episodes-grid"> … first \n      </div> after it
GRID_OPEN  = '<div class="episodes-grid">'
GRID_CLOSE = '\n      </div>'

SECTION_RE = re.compile(
    re.escape(GRID_OPEN) + r'(.*?)' + re.escape(GRID_CLOSE),
    re.DOTALL
)


def generate_grid_content(ep_index, cards_config):
    """Return the inner HTML content for <div class="episodes-grid">…</div>."""
    parts = []
    for card in cards_config:
        slug = card["slug"]
        if slug not in ep_index:
            raise ValueError(f"Slug not found in episode index: {slug!r}")
        ep_data = ep_index[slug]
        guest = card.get("guest_display") or ep_data["guest"]
        parts.append(make_card(
            slug       = slug,
            ep         = ep_data["ep"],
            guest      = guest,
            yt_id      = ep_data["yt_id"],
            card_title = card["card_title"],
            card_desc  = card["card_desc"],
        ))
    # Join cards with a blank line between each
    return "\n\n".join(parts)


def apply_replacement(html, topic_slug, new_content):
    matches = SECTION_RE.findall(html)
    if len(matches) != 1:
        raise ValueError(
            f"{topic_slug}: expected 1 episodes-grid section, found {len(matches)}"
        )
    replacement = GRID_OPEN + "\n" + new_content + GRID_CLOSE
    return SECTION_RE.sub(replacement, html, count=1)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    do_apply = len(sys.argv) > 1 and sys.argv[1] == "--apply"

    ep_index, skipped = build_ep_index()
    print(f"Episode index: {len(ep_index)} episodes loaded\n")

    errors  = []
    results = {}

    # A skipped episode means broken/reordered JSON-LD (GAPS #7). Tolerable to
    # note in a dry-run; a hard failure when actually writing files.
    if skipped and do_apply:
        errors.append(f"incomplete JSON-LD/embed in: {', '.join(skipped)} - "
                      "fix the episode page(s); refusing to --apply")

    for topic_slug, cards_config in TOPICS.items():
        topic_file = TOPIC_DIR / f"{topic_slug}.html"
        if not topic_file.exists():
            errors.append(f"MISSING file: {topic_file}")
            continue

        html = topic_file.read_text(encoding="utf-8")

        try:
            new_content = generate_grid_content(ep_index, cards_config)
            new_html    = apply_replacement(html, topic_slug, new_content)
        except ValueError as e:
            errors.append(str(e))
            continue

        changed = new_html != html
        results[topic_slug] = (topic_file, new_html, changed)

        status = "CHANGED" if changed else "no-op"
        print(f"  {status:8}  {topic_slug}  ({len(cards_config)} cards)")

        if changed and not do_apply:
            # Show what changed (guest names + slugs only)
            old_guests = re.findall(r'class="episode-card-guest">([^<]+)<', html)
            new_guests = re.findall(r'class="episode-card-guest">([^<]+)<', new_html)
            if old_guests != new_guests:
                print(f"             guests: {old_guests}  →  {new_guests}")

    print()
    if errors:
        print("ERRORS:")
        for e in errors:
            print(f"  {e}")
        sys.exit(1)

    if do_apply:
        written = 0
        for slug, (f, html, changed) in results.items():
            if changed:
                f.write_text(html, encoding="utf-8")
                written += 1
        print(f"Applied to {written} file(s).")
    else:
        print("Dry-run OK — re-run with --apply to write.")


if __name__ == "__main__":
    main()
