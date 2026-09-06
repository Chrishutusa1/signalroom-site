# CLAUDE.md — signalroom-site

Static HTML site for The Signal Room podcast (signalroompodcast.com). **No build system, no framework, no package.json.** Read [PROJECT.md](PROJECT.md) for architecture and data flow; read [GAPS.md](GAPS.md) for the known-issues audit before "fixing" anything that looks odd — it may be listed there with a scoped fix.

## Commands

```bash
# Local preview (or use the "signalroom-site" entry in .claude/launch.json)
npx serve -p 4200 .

# Publish gate — run on every new/edited episode page (exit != 0 blocks deploy)
python _validate_episode.py episodes/<slug>.html          # check: meta<=155, title<=57, shorts alt
python _validate_episode.py episodes/<slug>.html --fix    # auto-trim meta / backfill alt

# Site-wide title/meta gate (every page, not just episodes) - also a CI gate
python _validate_meta.py                                  # all pages; exit 1 on any violation
python _validate_meta.py <path>.html                      # just these files

# Normalize before deploy (dry-run by default; --apply to write)
python signalroom-publish-normalize.py --fix-alt --apply

# Refresh homepage stats + Featured Guests after adding/removing an episode
python _update_stats.py

# Regenerate topic-page episode grids (edit TOPICS dict in the script to add entries)
python _generate_topic_cards.py --apply

# Regenerate sitemap.xml from the pages on disk (CI fails if it's stale)
python _generate_sitemap.py --apply

# Deploy: STAGING = push to origin/main -> auto-deploys signalroom-staging.netlify.app (site 75176784)
# Deploy: PRODUCTION = merge to `main` -> auto-deploys signalroompodcast.com (site 98c71b47).
#   As of 2026-07-15 the prod site's production branch is `main` (the 2026-07-12 main->production
#   gate was DROPPED), so every merge to main deploys straight to prod, same as staging. The
#   approval gate is now merge-time: PR review + validate.yml CI + staging preview BEFORE merge.
#   Do NOT `netlify deploy --prod --dir=.` — let the git-connected build publish.
#   (History: prod deployed from a separate `production` branch via `git push origin main:production`
#    between 2026-07-12 and 2026-07-15; that branch/promotion is retired.)

# After a merge to main reaches prod: ping IndexNow for new/changed URLs
python signalroom-publish-normalize.py --indexnow --url https://signalroompodcast.com/episodes/<slug> --apply

# Airtable sync from Buzzsprout (secrets in C:\Users\PC\Desktop\HDSC\SignalRoom\.env)
python signalroom-airtable-bridge.py            # dry-run
python signalroom-airtable-bridge.py --apply
```

There are no tests and no lint. Python scripts are stdlib-only — keep them that way.

## New-page checklist (all three are mandatory)

1. Self-referential extensionless `<link rel="canonical" href="https://signalroompodcast.com/...">`.
2. Add `/<path>.html  /<path>  301!` line to `_redirects`.
3. Run `python _generate_sitemap.py --apply` (never hand-edit `sitemap.xml` entries; CI fails if it's stale). A brand-new ROOT page also needs a curated changefreq/priority in the script's `PAGE_META`.

New **episode** additionally: run `_validate_episode.py`, `_update_stats.py`, add to the relevant topic in `_generate_topic_cards.py`, add the guest's LinkedIn URL to `js/linkedin-links.js`, thumbnail/og:image must be the real YouTube `maxresdefault.jpg` (never generated), and after prod deploy ping IndexNow. Before ANY SEO-surface change (canonicals, redirects, sitemap, titles/metas, indexing requests), invoke the `gsc-change-preflight` skill.

## Conventions

- **Canonical URLs:** apex host (never www), https, extensionless (`/episodes/foo`). Articles are lowercase `/articles/...` in URLs but the files live in capital-A `Articles/` on disk — never link `href="/Articles/..."`, never rename the directory.
- **Every HTML page is standalone** — nav, footer, GA block, fonts block are duplicated per file. A site-wide chrome change means editing every file (write a small stdlib-Python pass over `**/*.html`, dry-run first — the repo's rollout convention).
- **Hard limits (publish gates):** `<meta name="description">` ≤ 155 chars; `<title>` ≤ 57 chars; every shorts-carousel `<img>` alt equals its `data-short-title`.
- **Mutating scripts are dry-run by default** with `--apply` to act. Follow this in any new script.
- **Styling:** shared chrome in `css/style.css` (CSS variables: `--purple-primary: #6C5CE7`, `--navy: #1A1A2E`, etc.); episode-body content uses inline styles. Prefer the variables in new work.
- Episode pages carry three JSON-LD blocks: `PodcastEpisode`, `FAQPage` (2 curated Q&As), `BreadcrumbList`. Homepage carries `PodcastSeries` bound to Wikidata `Q139555656` and a Person schema with a `disambiguatingDescription` (there is an identically-named personal-finance Chris Hutchins — do not remove it).

## Gotchas

- **Prod and staging both deploy from `main`.** signalroompodcast.com (site 98c71b47) and signalroom-staging.netlify.app (site 75176784) both auto-deploy from `main` (prod's production branch was switched back to `main` on 2026-07-15, dropping the 2026-07-12 gate). A merge to `main` now deploys to BOTH; the approval gate is the PR + CI + staging-preview *before* merge. When debugging "prod shows X", curl the live site — prod may briefly lag `main` during the build. (The old `production` branch is retired; do not `git push origin main:production`.)
- **The HTML is a machine interface.** Scripts locate content by exact regex on markup: `class="guest-card-name"`, `id="episode-count"`, the phrases "N episodes published to date" / "N healthcare AI practitioners", JSON-LD key order (`episodeNumber`, Person `name`), `data-short-title`, and the `<div class="guests-grid">` block in index.html. Reformatting or rewording these breaks `_update_stats.py`, `_update_featured_guests.py`, and `_generate_topic_cards.py` — since the GAPS #7 hardening they fail loudly (non-zero exit) instead of silently doing nothing.
- **Don't hand-edit script-owned blocks:** homepage stat counters, Featured Guests grid, topic-page episode grids. Edit the source (guests.html cards, episode JSON-LD, the TOPICS dict) and rerun the script.
- **Four root scripts are gitignored** (`/*.py` rule): `_validate_episode.py`, `signalroom-publish-normalize.py`, `_update_stats.py`, `_update_featured_guests.py`. `git status` looks clean without them; a fresh clone won't have them (GAPS.md #1 has the fix).
- **CSS is cached 1 year immutable.** Any `css/style.css` change requires bumping the `?v=` query on the `<link>` in **every** HTML file (currently `v=20260712` everywhere; CI fails if more than one value is live). Same rule applies to `/js/*`.
- **GA4 (`G-RZNHLJSRW3`) is deliberately deferred and hostname-gated** to production only. Never replace the loader with a plain script tag; never remove the hostname check.
- **The shorts carousel is absent on brand-new episode pages** — it's injected by a later cloud pass after clips are cut. Not a bug. After that pass, run `signalroom-publish-normalize.py --fix-alt --apply` (the cloud template emits empty alts).
- **The "add-podcast-episode" routine lives on claude.ai, not in this repo.** When Chris says an episode is "ready to push", the page usually already exists on staging — the remaining work is prod deploy + any missing `_redirects` line + IndexNow, not a rebuild.
- `1577c9c65cc397ca183ed80f92e0f9cf.txt` at root is the IndexNow key file. It is public by design. Do not delete, rename, or "move it somewhere safer".
- YouTube video IDs are matched to episodes by **guest name + publish date**, never by title (YouTube titles diverge from Buzzsprout titles) — see `signalroom-airtable-bridge.py`.
- `data/*.csv` are stale March–April 2026 exports; nothing reads them at runtime.

## Property Manager app (internal tool)

- `app/properties/index.html` (noindex; deliberately NOT in sitemap.xml or `_redirects` — the new-page checklist does not apply to it) + `netlify/functions/properties-data.mjs` (Functions v2, served at `/api/properties-data`). The function is **zero-dependency by design** (plain `fetch` against the Airtable REST API) — the repo still has no package.json; keep it that way.
- Storage: Airtable base `appgNkAc7lFFUi086` ("Property Manager": Properties / Agents / Meta tables). Rows may be edited directly in Airtable; the app picks them up on next load.
- Env vars on BOTH Netlify sites (prod 98c71b47, staging 75176784): `PROPERTIES_SYNC_KEY` (shared secret the app sends as `X-Sync-Key`; set 2026-07-16) and `AIRTABLE_TOKEN` (PAT scoped to that base, `data.records:read`+`write`). If either is missing the endpoint returns 503 and the app runs local-only.

## Never change without care

- `_redirects` — the canonical-URL contract; a bad line can loop or 404 the site. Append-only in practice; keep the `pattern  target  301!` shape.
- `netlify.toml` — caching + security headers + functions wiring.
- `sitemap.xml` — generated by `_generate_sitemap.py` (URL rules + changefreq/priority live in the script; lastmod is preserved on regeneration, `--touch <url>` resets one). Don't hand-edit entries.
- Canonical/OG/JSON-LD in any `<head>` — SEO is this site's job #1; run the preflight skill first.
- `netlify/functions/submission-created.js` — the guest-lead pipeline; it intentionally always returns 200 (prevents Netlify retry duplicates). Keep that contract.
- `robots.txt` and the IndexNow key file.
