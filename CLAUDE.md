# CLAUDE.md — signalroom-site

Static HTML site for The Signal Room podcast (signalroompodcast.com). **No build system, no framework, no package.json.** Read [PROJECT.md](PROJECT.md) for architecture and data flow; read [GAPS.md](GAPS.md) for the known-issues audit before "fixing" anything that looks odd — it may be listed there with a scoped fix.

## Commands

```bash
# Local preview (or use the "signalroom-site" entry in .claude/launch.json)
npx serve -p 4200 .

# Publish gate — run on every new/edited episode page (exit != 0 blocks deploy)
python _validate_episode.py episodes/<slug>.html          # check: meta<=155, title<=57, shorts alt
python _validate_episode.py episodes/<slug>.html --fix    # auto-trim meta / backfill alt

# Normalize before deploy (dry-run by default; --apply to write)
python signalroom-publish-normalize.py --fix-alt --apply

# Refresh homepage stats + Featured Guests after adding/removing an episode
python _update_stats.py

# Regenerate topic-page episode grids (edit TOPICS dict in the script to add entries)
python _generate_topic_cards.py --apply

# Deploy: staging = just push to origin/main (auto-deploys to signalroom-staging.netlify.app)
# Deploy: PRODUCTION (manual, deploys current disk state). MUST pass the gate first:
python _predeploy_check.py   # requires clean tree AND HEAD == origin/main
netlify deploy --prod --site=98c71b47-cb1e-4eb2-8255-963349df8ccf --dir=.

# After prod deploy: ping IndexNow for new/changed URLs
python signalroom-publish-normalize.py --indexnow --url https://signalroompodcast.com/episodes/<slug> --apply

# Airtable sync from Buzzsprout (secrets in C:\Users\PC\Desktop\HDSC\SignalRoom\.env)
python signalroom-airtable-bridge.py            # dry-run
python signalroom-airtable-bridge.py --apply
```

There are no tests and no lint. Python scripts are stdlib-only — keep them that way.

## New-page checklist (all three are manual and all three are mandatory)

1. Self-referential extensionless `<link rel="canonical" href="https://signalroompodcast.com/...">`.
2. Add `/<path>.html  /<path>  301!` line to `_redirects`.
3. Add extensionless `<loc>` to `sitemap.xml`.

New **episode** additionally: run `_validate_episode.py`, `_update_stats.py`, add to the relevant topic in `_generate_topic_cards.py`, add the guest's LinkedIn URL to `js/linkedin-links.js`, thumbnail/og:image must be the real YouTube `maxresdefault.jpg` (never generated), and after prod deploy ping IndexNow. Before ANY SEO-surface change (canonicals, redirects, sitemap, titles/metas, indexing requests), invoke the `gsc-change-preflight` skill.

## Conventions

- **Canonical URLs:** apex host (never www), https, extensionless (`/episodes/foo`). Articles are lowercase `/articles/...` in URLs but the files live in capital-A `Articles/` on disk — never link `href="/Articles/..."`, never rename the directory.
- **Every HTML page is standalone** — nav, footer, GA block, fonts block are duplicated per file. A site-wide chrome change means editing every file (see `.claude/rollout_perf_edits.py` for the bulk-edit pattern).
- **Hard limits (publish gates):** `<meta name="description">` ≤ 155 chars; `<title>` ≤ 57 chars; every shorts-carousel `<img>` alt equals its `data-short-title`.
- **Mutating scripts are dry-run by default** with `--apply` to act. Follow this in any new script.
- **Styling:** shared chrome in `css/style.css` (CSS variables: `--purple-primary: #6C5CE7`, `--navy: #1A1A2E`, etc.); episode-body content uses inline styles. Prefer the variables in new work.
- Episode pages carry three JSON-LD blocks: `PodcastEpisode`, `FAQPage` (2 curated Q&As), `BreadcrumbList`. Homepage carries `PodcastSeries` bound to Wikidata `Q139555656` and a Person schema with a `disambiguatingDescription` (there is an identically-named personal-finance Chris Hutchins — do not remove it).

## Gotchas

- **Prod ≠ git.** Production is a manual directory deploy; staging follows origin/main. When debugging "prod shows X", curl the live site — don't trust the repo, and don't trust prod to have the latest commit.
- **The HTML is a machine interface.** Scripts locate content by exact regex on markup: `class="guest-card-name"`, `id="episode-count"`, the phrases "See All N Episodes" / "N episodes published to date" / "N healthcare AI practitioners", JSON-LD key order (`episodeNumber`, Person `name`), `data-short-title`, and the `<div class="guests-grid">` block in index.html. Reformatting or rewording these breaks `_update_stats.py`, `_update_featured_guests.py`, and `_generate_topic_cards.py` — sometimes silently.
- **Don't hand-edit script-owned blocks:** homepage stat counters, Featured Guests grid, topic-page episode grids. Edit the source (guests.html cards, episode JSON-LD, the TOPICS dict) and rerun the script.
- **Four root scripts are gitignored** (`/*.py` rule): `_validate_episode.py`, `signalroom-publish-normalize.py`, `_update_stats.py`, `_update_featured_guests.py`. `git status` looks clean without them; a fresh clone won't have them (GAPS.md #1 has the fix).
- **CSS is cached 1 year immutable.** Any `css/style.css` change requires bumping the `?v=` query on the `<link>` in **every** HTML file — and three different `?v=` values are currently live (GAPS.md #4). Same rule applies to `/js/*`.
- **GA4 (`G-RZNHLJSRW3`) is deliberately deferred and hostname-gated** to production only. Never replace the loader with a plain script tag; never remove the hostname check.
- **The shorts carousel is absent on brand-new episode pages** — it's injected by a later cloud pass after clips are cut. Not a bug. After that pass, run `signalroom-publish-normalize.py --fix-alt --apply` (the cloud template emits empty alts).
- **The "add-podcast-episode" routine lives on claude.ai, not in this repo.** When Chris says an episode is "ready to push", the page usually already exists on staging — the remaining work is prod deploy + any missing `_redirects` line + IndexNow, not a rebuild.
- `1577c9c65cc397ca183ed80f92e0f9cf.txt` at root is the IndexNow key file. It is public by design. Do not delete, rename, or "move it somewhere safer".
- `.claude/finalize_ep27.py` and `.claude/rollout_perf_edits.py` are **historical one-shots** — pattern references only, do not run them.
- YouTube video IDs are matched to episodes by **guest name + publish date**, never by title (YouTube titles diverge from Buzzsprout titles) — see `signalroom-airtable-bridge.py`.
- `data/*.csv` are stale March–April 2026 exports; nothing reads them at runtime.

## Never change without care

- `_redirects` — the canonical-URL contract; a bad line can loop or 404 the site. Append-only in practice; keep the `pattern  target  301!` shape.
- `netlify.toml` — caching + security headers + functions wiring.
- `sitemap.xml` — manual; keep every entry apex + extensionless.
- Canonical/OG/JSON-LD in any `<head>` — SEO is this site's job #1; run the preflight skill first.
- `netlify/functions/submission-created.js` — the guest-lead pipeline; it intentionally always returns 200 (prevents Netlify retry duplicates). Keep that contract.
- `robots.txt` and the IndexNow key file.
