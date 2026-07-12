"""_update_featured_guests.py — rebuild the homepage "Featured Guests" block from
the NEWEST 3 guests (top of guests.html), so it auto-tracks new episodes.

Per featured card: photo/name/role/topic pulled from guests.html; the one-line
insight pulled from that episode page's <meta name="description">. The "more" card
shows the live unique-guest count. Idempotent. Run from the repo root (the homepage
refresh routine runs this alongside _update_stats.py)."""
import re
from pathlib import Path

ROOT = Path(__file__).parent
GUESTS = (ROOT / "guests.html").read_text(encoding="utf-8")
INDEX = ROOT / "index.html"


def first_n_guest_cards(n=3):
    blocks = GUESTS.split('<div class="guest-card-wrapper">')[1:]
    out = []
    for b in blocks[:n]:
        slug = re.search(r'href="(/episodes/[^"]+)" class="guest-card"', b)
        photo = re.search(r'class="guest-card-photo-wrap">\s*<img src="([^"]+)"', b)
        name = re.search(r'class="guest-card-name">([^<]+)<', b)
        role = re.search(r'class="guest-card-role">([^<]+)<', b)
        topic = re.search(r'class="guest-card-topic">([^<]+)<', b)
        if not (slug and photo and name and role and topic):
            continue
        out.append({"slug": slug.group(1), "photo": photo.group(1),
                    "name": name.group(1).strip(), "role": role.group(1).strip(),
                    "topic": topic.group(1).strip()})
    return out


def insight_for(slug):
    """One-line insight = the episode page's meta description (curated per episode)."""
    p = ROOT / (slug.lstrip("/") + ".html")
    if not p.exists():
        return ""
    m = re.search(r'<meta name="description" content="([^"]+)"', p.read_text(encoding="utf-8"))
    return m.group(1).strip() if m else ""


def unique_guest_count():
    return len({n.strip() for n in re.findall(r'class="guest-card-name">([^<]+)</h3>', GUESTS)})


def card_html(g):
    return (
        f'        <a href="{g["slug"]}" class="guest-card">\n'
        f'          <img class="guest-card-photo" src="{g["photo"]}" alt="{g["name"]}" loading="lazy" width="400" height="400">\n'
        f'          <div class="guest-card-name">{g["name"]}</div>\n'
        f'          <div class="guest-card-role">{g["role"]}</div>\n'
        f'          <div class="guest-card-topic">{g["topic"]}</div>\n'
        f'          <div class="guest-card-insight">{insight_for(g["slug"])}</div>\n'
        f'        </a>\n'
    )


def main():
    guests = first_n_guest_cards(3)
    count = unique_guest_count()
    cards = "".join(card_html(g) for g in guests)
    more = (
        f'        <a href="/guests" class="guest-card guest-card--more" style="background:var(--purple-mist);">\n'
        f'          <div>\n'
        f'            <div class="guest-card-name" style="font-size:2rem;color:var(--purple-primary);margin-bottom:0.5rem;">{count}+</div>\n'
        f'            <div class="guest-card-role">Healthcare leaders and counting</div>\n'
        f'            <div class="guest-card-topic" style="margin-top:1rem;">View All Guests &rarr;</div>\n'
        f'          </div>\n'
        f'        </a>\n'
    )
    new_inner = "\n" + cards + more + "      "

    html = INDEX.read_text(encoding="utf-8")
    pat = re.compile(r'(<div class="guests-grid">)(.*?)(</div>\s*</div>\s*</section>)', re.S)
    new, n = pat.subn(lambda m: m.group(1) + new_inner + m.group(3), html, count=1)
    if n != 1:
        raise SystemExit("ERROR: featured guests-grid block not matched")
    INDEX.write_text(new, encoding="utf-8")
    print("Featured guests ->", ", ".join(g["name"] for g in guests), f"| more card: {count}+")


if __name__ == "__main__":
    main()
