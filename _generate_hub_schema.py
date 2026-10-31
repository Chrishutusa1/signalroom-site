"""Generate CollectionPage + ItemList JSON-LD for the /episodes and /guests hub pages.

The ItemList is built from each page's own cards, so it cannot drift from what the page
shows. (The hand-written ItemList on /articles/ is an example of the alternative: it lists
2 of the page's 37 articles.) The block sits in <head> between two marker comments:

    <!-- hub-schema:start -->  ...  <!-- hub-schema:end -->

Usage (stdlib only; dry-run by default, like the other scripts here):
    python _generate_hub_schema.py            # report what would change
    python _generate_hub_schema.py --apply    # write the blocks
    python _generate_hub_schema.py --check    # exit 1 if any block is missing or stale

Run it after adding or removing an episode card on either hub. It fails loudly (non-zero
exit) if the cards it expects are not found, rather than silently emitting an empty list.
"""
import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SITE = "https://signalroompodcast.com"
START, END = "<!-- hub-schema:start -->", "<!-- hub-schema:end -->"

PUBLISHER = {
    "@type": "Organization",
    "name": "The Signal Room",
    "url": SITE,
    "logo": {"@type": "ImageObject", "url": SITE + "/assets/logos/Signal_Room_Cover_FINAL_v2.png"},
}
PART_OF = {"@type": "WebSite", "@id": SITE + "/#website", "name": "The Signal Room", "url": SITE}
ABOUT = {"@type": "PodcastSeries", "@id": SITE + "/#podcast", "name": "The Signal Room", "url": SITE}


def text(fragment):
    return html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", fragment))).strip()


def meta_description(page):
    m = re.search(r'<meta name="description" content="(.*?)"', page)
    if not m:
        raise SystemExit("no meta description found")
    return html.unescape(m.group(1))


def episode_items(page):
    starts = [m.start() for m in re.finditer(r'<div class="episode-card">', page)]
    items = []
    for i, s in enumerate(starts):
        chunk = page[s:starts[i + 1] if i + 1 < len(starts) else len(page)]
        num = re.search(r'<div class="episode-number">\s*(?:S(\d+)\s+)?Ep\s*(\d+)\s*</div>', chunk)
        overall = re.search(r'data-episode="(\d+)"', chunk)
        guest = re.search(r"<h3>(.*?)</h3>", chunk, re.S)
        title = re.search(r'<p class="episode-title">(.*?)</p>', chunk, re.S)
        href = re.search(r'href="(/episodes/[^"#?]+)"', chunk)
        if not (num and guest and title and href):
            raise SystemExit(f"episodes.html: card {i + 1} is missing number/guest/title/link")
        # Season 2 onward: the card shows "S<season> Ep <n>" and carries the series-wide
        # sequence in data-episode, which keeps ordering and uniqueness checks working.
        season, ep = num.group(1), int(num.group(2))
        n = int(overall.group(1)) if overall else ep
        label = f"Season {season}, Episode {ep}" if season else f"Episode {ep}"
        items.append((n, f"{label}: {text(title.group(1))} with {text(guest.group(1))}", SITE + href.group(1), None))
    return items


def guest_items(page):
    items = []
    for m in re.finditer(r'<a href="(/episodes/[^"#?]+)" class="guest-card"[^>]*data-episode="(\d+)">(.*?)</a>', page, re.S):
        href, n, body = m.group(1), int(m.group(2)), m.group(3)
        name = re.search(r'<h3 class="guest-card-name">(.*?)</h3>', body, re.S)
        topic = re.search(r'<p class="guest-card-topic">(.*?)</p>', body, re.S)
        if not (name and topic):
            raise SystemExit(f"guests.html: card for episode {n} is missing name/topic")
        badge = re.search(r'class="guest-card-episode-badge">\s*S(\d+)\s+EP\s*(\d+)\s*<', body)
        label = f"Season {badge.group(1)}, Episode {badge.group(2)}" if badge else f"Episode {n}"
        items.append((n, text(name.group(1)), SITE + href, f"Guest on {label}: {text(topic.group(1))}"))
    return items


HUBS = {
    "episodes.html": {
        "url": SITE + "/episodes",
        "name": "All Episodes of The Signal Room Podcast",
        "items": episode_items,
        "card_marker": 'class="episode-card">',
    },
    "guests.html": {
        "url": SITE + "/guests",
        "name": "Guests on The Signal Room Podcast",
        "items": guest_items,
        "card_marker": 'class="guest-card"',
    },
}


def build_block(page, spec):
    items = spec["items"](page)
    if not items:
        raise SystemExit("no cards found; refusing to emit an empty ItemList")
    nums = [n for n, *_ in items]
    if len(set(nums)) != len(nums):
        raise SystemExit("duplicate episode numbers among cards: " + str(sorted(x for x in nums if nums.count(x) > 1)))
    elements = []
    for pos, (n, name, url, desc) in enumerate(items, 1):
        el = {"@type": "ListItem", "position": pos, "url": url, "name": name}
        if desc:
            el["description"] = desc
        elements.append(el)
    itemlist = {"@type": "ItemList", "numberOfItems": len(elements), "itemListElement": elements}
    if nums == sorted(nums, reverse=True):
        itemlist["itemListOrder"] = "https://schema.org/ItemListOrderDescending"
    data = {
        "@context": "https://schema.org",
        "@type": "CollectionPage",
        "name": spec["name"],
        "description": meta_description(page),
        "url": spec["url"],
        "isPartOf": PART_OF,
        "about": ABOUT,
        "publisher": PUBLISHER,
        "mainEntity": itemlist,
    }
    body = json.dumps(data, indent=2, ensure_ascii=False)
    return f'{START}\n<script type="application/ld+json">\n{body}\n</script>\n{END}\n', len(elements)


def render(page, block):
    if START in page and END in page:
        return re.sub(re.escape(START) + r".*?" + re.escape(END) + r"\n?", lambda _: block, page, count=1, flags=re.S)
    if START in page or END in page:
        raise SystemExit("only one hub-schema marker found; fix the markers by hand")
    if page.count("</head>") != 1:
        raise SystemExit("expected exactly one </head>")
    return page.replace("</head>", block + "</head>", 1)


def main(argv):
    apply, check = "--apply" in argv, "--check" in argv
    stale = 0
    for fname, spec in HUBS.items():
        path = ROOT / fname
        raw = path.read_bytes().decode("utf-8")
        crlf = "\r\n" in raw
        page = raw.replace("\r\n", "\n")
        block, n = build_block(page, spec)
        new = render(page, block)
        state = "up to date" if new == page else ("missing" if START not in page else "STALE")
        print(f"{fname}: {n} items -> {state}")
        if new != page:
            stale += 1
            if apply:
                path.write_bytes((new.replace("\n", "\r\n") if crlf else new).encode("utf-8"))
                print(f"  wrote {fname}")
    if check and stale:
        print("hub schema is missing or out of date: run `python _generate_hub_schema.py --apply`")
        return 1
    if stale and not apply:
        print("(dry run: re-run with --apply to write)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
