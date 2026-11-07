"""Exercise generated counts and current-episode selection across a release date."""
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class PublishedStatsTest(unittest.TestCase):
    def test_future_episode_is_counted_only_after_release(self):
        source = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ("_update_stats.py", "_update_featured_guests.py", "index.html",
                         "guests.html", "about.html", "be-a-guest.html"):
                shutil.copy2(source / name, root / name)
            shutil.copytree(source / "episodes", root / "episodes")
            pages = list((root / "episodes").glob("*.html"))
            numbered = []
            for page in pages:
                text = page.read_text(encoding="utf-8")
                number = int(re.search(r'"episodeNumber"\s*:\s*"?(\d+)', text)[1])
                numbered.append((number, page))
                page.write_text(re.sub(r'"datePublished"\s*:\s*"[^"]+"',
                                       '"datePublished": "2000-01-01T00:00:00-06:00"', text), encoding="utf-8")
            numbered.sort()
            latest = numbered[-1][1]
            past = latest.read_text(encoding="utf-8")
            latest.write_text(past.replace("2000-01-01T00:00:00-06:00", "2099-01-01T00:00:00-06:00"), encoding="utf-8")
            for expected_count, expected_slug in ((len(pages)-1, numbered[-2][1].stem),
                                                   (len(pages), latest.stem)):
                subprocess.run([sys.executable, str(root / "_update_stats.py")], check=True,
                               capture_output=True, text=True, encoding="utf-8")
                home = (root / "index.html").read_text(encoding="utf-8")
                self.assertIn(f'id="episode-count">{expected_count}<', home)
                self.assertIn(f'{expected_count} episodes published to date', home)
                self.assertIn(f'href="/episodes/{expected_slug}" class="btn btn-outline" id="current-episode-cta"', home)
                latest.write_text(past, encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
