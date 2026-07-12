"""
_update_stats.py — keep the homepage stat bar + guest counts in sync with the site.

Derives the numbers from the repo itself (no API keys, never stale relative to content):
  - Episode count   = number of episodes/*.html pages
  - Guest count     = unique guest names in guests.html (dedup; one card per episode)

Rewrites the count tokens in index.html and guests.html. Idempotent.
Run from the repo root after adding/removing an episode (the add-podcast-episode flow
should call this). Gitignored local helper, same convention as _pathb_sweep.py.
"""
import glob
import re
from pathlib import Path

ROOT = Path(__file__).parent

ep_count = len(glob.glob(str(ROOT / "episodes" / "*.html")))

guests_html = (ROOT / "guests.html").read_text(encoding="utf-8")
names = re.findall(r'class="guest-card-name">([^<]+)</h3>', guests_html)
guest_count = len({n.strip() for n in names})

# --- index.html ---
idx_path = ROOT / "index.html"
idx = idx_path.read_text(encoding="utf-8")
idx, n1 = re.subn(r'(id="episode-count">)\d+\+?(<)', rf'\g<1>{ep_count}\g<2>', idx)
idx, n2 = re.subn(r'(id="guest-count">)\d+\+?(<)', rf'\g<1>{guest_count}\g<2>', idx)
# ("See All N Episodes" was a synced phrase until 07bbd28 reworded the hero CTA
# to the count-less "View All Episodes" - no longer a sync target.)
idx, n4 = re.subn(r'\d+ episodes published to date', f'{ep_count} episodes published to date', idx)

# --- guests.html (og:description + hero copy both say "N healthcare AI practitioners") ---
gh, n5 = re.subn(r'\d+ healthcare AI practitioners', f'{guest_count} healthcare AI practitioners', guests_html)

print(f"episodes={ep_count} guests={guest_count}")
print(f"index.html: episode-count={n1} guest-count={n2} published-to-date={n4}")
print(f"guests.html: practitioner-count={n5}")

# A zero substitution count means the anchor markup/phrase this script keys on
# was reworded — the counters would silently drift stale (GAPS #7). Fail hard
# and write nothing rather than leave the pages half-updated.
zeros = [label for label, n in [
    ('index.html id="episode-count"', n1),
    ('index.html id="guest-count"', n2),
    ('index.html "N episodes published to date"', n4),
    ('guests.html "N healthcare AI practitioners"', n5),
] if n == 0]
if zeros:
    raise SystemExit("ERROR: anchor pattern(s) not found - markup was reworded? "
                     "Nothing written.\n  - " + "\n  - ".join(zeros))

idx_path.write_text(idx, encoding="utf-8")
(ROOT / "guests.html").write_text(gh, encoding="utf-8")

# Also refresh the homepage "Featured Guests" block (newest 3 guests).
import runpy  # noqa: E402
runpy.run_path(str(ROOT / "_update_featured_guests.py"), run_name="__main__")
