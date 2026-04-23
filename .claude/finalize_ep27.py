"""
Finalize EP 27 (Sid Dutta) scaffold into a deployable episode.

Run AFTER the Buzzsprout + YouTube uploads are live.

Usage:
    python .claude/finalize_ep27.py <BUZZSPROUT_ID> <YOUTUBE_ID> <YYYY-MM-DD> <DURATION_MINUTES>

Example:
    python .claude/finalize_ep27.py 19123456 XYZabc123 2026-04-30 65

What it does (all relative to the signalroom-site repo root):
  1. Replaces placeholders in episodes/ai-strategy-stalls-data-layer.html
  2. Bumps index.html hero CTA + episode count stat (26 -> 27)
  3. Inserts EP 27 card into the homepage Latest Episodes grid
  4. Inserts EP 27 card into episodes.html grid
  5. Inserts Sid Dutta card into guests.html grid
  6. Stages + commits + pushes to origin/main (staging auto-deploys)

It does NOT deploy to production. Run the usual netlify CLI prod deploy
after staging looks good.

The script is safe to re-run: it checks for existing EP 27 markers before
inserting, and the placeholder replacement is a no-op if values are
already filled in.
"""
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

EP_SLUG = "ai-strategy-stalls-data-layer"
EP_NUMBER = 27
GUEST_NAME = "Sid Dutta"
GUEST_ROLE = "Founder & CEO, PrivateClave AI"
GUEST_PHOTO = "sid-dutta.jpg"
EP_TITLE_FULL = "AI Strategy Stalls at the Data Layer: Privacy-Preserving AI & Governance for Healthcare"
EP_CARD_DESC = "Why most healthcare AI initiatives never leave pilot — and how runtime AI governance, privacy-preserving AI, and data clean rooms change what leaders can actually ship."
GUEST_CATEGORIES = "ai-governance,cybersecurity"


def die(msg, code=1):
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(code)


def main():
    if len(sys.argv) != 5:
        print(__doc__)
        die("usage: python .claude/finalize_ep27.py <BZ_ID> <YT_ID> <YYYY-MM-DD> <DURATION_MINUTES>")

    bz_id, yt_id, pub_date, duration_min = sys.argv[1:5]

    try:
        dt = datetime.strptime(pub_date, "%Y-%m-%d")
    except ValueError:
        die(f"publish date must be YYYY-MM-DD, got: {pub_date}")
    date_display = dt.strftime("%B %-d, %Y") if os.name != "nt" else dt.strftime("%B ") + str(dt.day) + dt.strftime(", %Y")

    try:
        duration_min = int(duration_min)
    except ValueError:
        die(f"duration must be an integer number of minutes, got: {duration_min}")

    ep_page = REPO_ROOT / "episodes" / f"{EP_SLUG}.html"
    if not ep_page.exists():
        die(f"episode page not scaffolded at {ep_page}")

    # --- 1. Fill in placeholders on the episode page ---
    html = ep_page.read_text(encoding="utf-8")
    replacements = {
        "__BZ_ID__": bz_id,
        "__YT_ID__": yt_id,
        "__PUBLISH_DATE__": pub_date,
        "__PUBLISH_DATE_DISPLAY__": date_display,
        "__DURATION_MINUTES__": str(duration_min),
    }
    for k, v in replacements.items():
        html = html.replace(k, v)
    ep_page.write_text(html, encoding="utf-8")
    print(f"[1/5] episode page placeholders filled: {ep_page.name}")

    # --- 2. index.html: bump hero CTA + counts, insert card ---
    idx = REPO_ROOT / "index.html"
    idx_html = idx.read_text(encoding="utf-8")
    orig_idx = idx_html

    idx_html = idx_html.replace(
        'href="https://signalroompodcast.com/episodes/healthcare-losing-best-people.html" class="btn btn-primary">Watch Episode 26 Now',
        f'href="https://signalroompodcast.com/episodes/{EP_SLUG}.html" class="btn btn-primary">Watch Episode {EP_NUMBER} Now',
    )
    idx_html = idx_html.replace(
        ">See All 26 Episodes<",
        f">See All {EP_NUMBER} Episodes<",
    )
    idx_html = re.sub(
        r'(<div class="stat-number" id="episode-count">)\d+(</div>)',
        rf"\g<1>{EP_NUMBER}\g<2>",
        idx_html,
    )

    # Insert EP 27 card just before the Poonam Patel (EP 26) card
    ep27_homepage_card = f'''        <a href="https://signalroompodcast.com/episodes/{EP_SLUG}.html" class="episode-card">
          <div class="episode-card-thumb">
            <img src="https://img.youtube.com/vi/{yt_id}/hqdefault.jpg" alt="{GUEST_NAME} episode" loading="lazy" width="480" height="360">
            <div class="episode-card-play"><svg viewBox="0 0 24 24"><polygon points="5,3 19,12 5,21"/></svg></div>
          </div>
          <div class="episode-card-body">
            <div class="episode-tags">
              <span class="episode-tag">AI Governance</span>
              <span class="episode-tag">Data Security</span>
            </div>
            <div class="episode-card-guest">{GUEST_NAME}</div>
            <div class="episode-card-title">{EP_TITLE_FULL}</div>
            <div class="episode-card-desc">{EP_CARD_DESC}</div>
            <div class="episode-card-footer">
              <span class="episode-card-ep">Episode {EP_NUMBER}</span>
              <span class="episode-card-link">Watch Now &rarr;</span>
            </div>
          </div>
        </a>

        '''

    if f'episodes/{EP_SLUG}.html" class="episode-card"' not in idx_html:
        anchor = '<a href="https://signalroompodcast.com/episodes/healthcare-losing-best-people.html" class="episode-card">'
        if anchor not in idx_html:
            die("could not locate EP 26 card on index.html to insert EP 27 before it")
        idx_html = idx_html.replace(anchor, ep27_homepage_card + anchor, 1)

    if idx_html != orig_idx:
        idx.write_text(idx_html, encoding="utf-8")
        print("[2/5] index.html updated (hero CTA, counts, new card)")
    else:
        print("[2/5] index.html already has EP 27 — skipped")

    # --- 3. episodes.html: insert new card before EP 26 ---
    eps = REPO_ROOT / "episodes.html"
    eps_html = eps.read_text(encoding="utf-8")
    orig_eps = eps_html

    ep27_episodes_card = f'''                    <!-- Episode {EP_NUMBER} -->
    <div class="episode-card">
      <div class="episode-thumbnail">
        <img src="https://img.youtube.com/vi/{yt_id}/hqdefault.jpg" alt="Episode {EP_NUMBER}: {GUEST_NAME}">
      </div>
      <div class="episode-card-content">
        <div class="episode-number">Ep {EP_NUMBER}</div>
        <h3>{GUEST_NAME}</h3>
        <p class="episode-title">{EP_TITLE_FULL}</p>
        <a class="listen-btn" href="https://signalroompodcast.com/episodes/{EP_SLUG}.html">Listen Now</a>
      </div>
    </div>

    '''

    if f'episodes/{EP_SLUG}.html' not in eps_html:
        marker = "<!-- Episode 26 -->"
        if marker not in eps_html:
            die("could not locate <!-- Episode 26 --> marker in episodes.html")
        eps_html = eps_html.replace(marker, ep27_episodes_card + marker, 1)

    if eps_html != orig_eps:
        eps.write_text(eps_html, encoding="utf-8")
        print("[3/5] episodes.html updated (new EP 27 card)")
    else:
        print("[3/5] episodes.html already has EP 27 — skipped")

    # --- 4. guests.html: insert Sid Dutta card before Poonam Patel (EP 26) ---
    gts = REPO_ROOT / "guests.html"
    gts_html = gts.read_text(encoding="utf-8")
    orig_gts = gts_html

    ep27_guest_card = f'''                    <a href="https://signalroompodcast.com/episodes/{EP_SLUG}.html" class="guest-card" data-categories="{GUEST_CATEGORIES}" data-episode="{EP_NUMBER}">
                        <div class="guest-card-photo-wrap">
                            <img src="assets/guests/{GUEST_PHOTO}" alt="{GUEST_NAME}" class="guest-card-photo">
                            <span class="guest-card-episode-badge">EP {EP_NUMBER}</span>
                        </div>
                        <h3 class="guest-card-name">{GUEST_NAME}</h3>
                        <p class="guest-card-role">{GUEST_ROLE}</p>
                        <p class="guest-card-topic">{EP_TITLE_FULL}</p>
                        <span class="guest-card-cta">Watch Episode <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M5 12h14M12 5l7 7-7 7"/></svg></span>
                    </a>

                    '''

    if f'data-episode="{EP_NUMBER}"' not in gts_html:
        anchor = '<a href="https://signalroompodcast.com/episodes/healthcare-losing-best-people.html" class="guest-card"'
        if anchor not in gts_html:
            die("could not locate Poonam Patel guest card to insert Sid Dutta before it")
        gts_html = gts_html.replace(anchor, ep27_guest_card + anchor, 1)

    if gts_html != orig_gts:
        gts.write_text(gts_html, encoding="utf-8")
        print("[4/5] guests.html updated (Sid Dutta card)")
    else:
        print("[4/5] guests.html already has Sid Dutta — skipped")

    # --- 5. git stage + commit + push ---
    def run(*args):
        return subprocess.run(args, cwd=REPO_ROOT, check=True, capture_output=True, text=True)

    run("git", "add",
        str(ep_page.relative_to(REPO_ROOT)),
        str(idx.relative_to(REPO_ROOT)),
        str(eps.relative_to(REPO_ROOT)),
        str(gts.relative_to(REPO_ROOT)),
        f"assets/guests/{GUEST_PHOTO}",
    )

    status = run("git", "status", "--porcelain").stdout.strip()
    if not status:
        print("[5/5] nothing to commit — everything already up to date")
        return

    commit_msg = f"EP {EP_NUMBER}: Sid Dutta — AI Strategy Stalls at the Data Layer (BZ {bz_id}, YT {yt_id})"
    run("git", "commit", "-m", commit_msg)
    run("git", "push", "origin", "main")
    print(f"[5/5] committed + pushed: {commit_msg}")
    print("\nDone. Staging will auto-deploy. Verify on signalroom-staging.netlify.app,")
    print("then push to prod with:")
    print("  cd $(git rev-parse --show-toplevel) && netlify deploy --prod \\")
    print("    --site=98c71b47-cb1e-4eb2-8255-963349df8ccf --dir=.")


if __name__ == "__main__":
    main()
