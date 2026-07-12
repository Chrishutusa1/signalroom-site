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
idx, n3 = re.subn(r'See All \d+ Episodes', f'See All {ep_count} Episodes', idx)
idx, n4 = re.subn(r'\d+ episodes published to date', f'{ep_count} episodes published to date', idx)
idx_path.write_text(idx, encoding="utf-8")

# --- guests.html (og:description + hero copy both say "N healthcare AI practitioners") ---
gh, n5 = re.subn(r'\d+ healthcare AI practitioners', f'{guest_count} healthcare AI practitioners', guests_html)
(ROOT / "guests.html").write_text(gh, encoding="utf-8")

print(f"episodes={ep_count} guests={guest_count}")
print(f"index.html: episode-count={n1} guest-count={n2} see-all={n3} published-to-date={n4}")
print(f"guests.html: practitioner-count={n5}")

# Also refresh the homepage "Featured Guests" block (newest 3 guests).
import runpy  # noqa: E402
runpy.run_path(str(ROOT / "_update_featured_guests.py"), run_name="__main__")
