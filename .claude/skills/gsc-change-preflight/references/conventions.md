# SEO-surface conventions — The Signal Room

Reference for the `gsc-change-preflight` skill. These are the contracts the
preflight's Step 2 checks against. They are drawn from the repo's `CLAUDE.md`
("Conventions", "Gotchas", "Never change without care") — if `CLAUDE.md` and
this file ever disagree, `CLAUDE.md` wins and this file should be updated.

## Canonical / OG URLs

- **Apex host only:** `https://signalroompodcast.com/...` — never `www`.
- **https**, always.
- **Extensionless:** `/episodes/foo`, never `/episodes/foo.html`.
- **Self-referential:** each page's `rel="canonical"` points to its own final
  URL, and `og:url` matches it.
- **Articles casing trap:** article URLs are lowercase `/articles/...`, but the
  files live in a capital-A `Articles/` directory on disk. Never link
  `href="/Articles/..."`, and never rename the directory.

## `_redirects`

- This file is the canonical-URL contract. A bad line can loop or 404 the whole
  site — treat it as append-only in practice.
- Shape of every rule: `pattern  target  301!` (the `!` forces the redirect even
  when a file exists at the pattern path).
- **Every new page** needs a `/<path>.html  /<path>  301!` line so the
  extension-bearing URL 301s to the canonical extensionless one.
- Before adding a line, check it doesn't shadow or loop against existing rules
  (does the target match an earlier pattern?).

## `sitemap.xml`

- **Generated only** by `_generate_sitemap.py`. Never hand-edit entries.
- CI fails if the sitemap is stale relative to the pages on disk.
- Commands:
  - `python _generate_sitemap.py --check` — exit 1 if stale (the CI gate).
  - `python _generate_sitemap.py --apply` — regenerate; `lastmod` is preserved.
  - `python _generate_sitemap.py --touch <url> --apply` — reset one page's
    `lastmod` to its git date.
- A brand-new **root** page needs a curated changefreq/priority entry added to
  the script's `PAGE_META` dict before regenerating.

## Titles & meta descriptions (publish gates)

- `<title>` ≤ **57** characters.
- `<meta name="description">` ≤ **155** characters.
- Episode pages: `python _validate_episode.py episodes/<slug>.html` enforces both
  limits plus the shorts-carousel alt rule; `--fix` word-trims the meta and
  backfills alts. Exit code ≠ 0 blocks deploy.
- These limits apply to the `description` meta only — not `og:description` or
  other surfaces.

## robots.txt & the IndexNow key file

- `robots.txt` almost never changes; any edit is high-risk (a stray `Disallow`
  can deindex sections of the site).
- The IndexNow key file (a hex-named `*.txt` at the repo root) is **public by
  design**. Do not delete, rename, or "move it somewhere safer" — the value in
  the file must match what's submitted in IndexNow pings.

## Indexing requests (IndexNow)

- Submit only **production** URLs, and only **after** the change has merged to
  `main` and the prod build has published — otherwise the ping just re-crawls
  the old content.
- Command (dry-run without `--apply`):
  `python signalroom-publish-normalize.py --indexnow --url https://signalroompodcast.com/<path> --apply`
- Success is HTTP 200 (accepted) or 202 (accepted/pending). Anything else is a
  failure.

## Deploy-flow context these checks assume

- **Prod and staging both deploy from `main`.** signalroompodcast.com (Netlify
  site 98c71b47) and signalroom-staging.netlify.app (75176784) both auto-deploy
  on merge to `main`. The approval gate is the PR review + `validate.yml` CI +
  staging preview **before** merge — so the preflight belongs *before* the
  change is written/merged, not after.
- The HTML is a machine interface: several scripts locate content by exact
  regex/phrase (`id="episode-count"`, `class="guest-card-name"`, JSON-LD key
  order, `data-short-title`). Rewording SEO-adjacent markup can break
  `_update_stats.py` / `_generate_topic_cards.py` even when it looks harmless —
  another reason to run tooling rather than hand-edit.
- **CSS/JS is cached 1 year immutable.** A `css/style.css` or `/js/*` change
  requires bumping the `?v=` query on the `<link>`/`<script>` in *every* HTML
  file (CI fails if more than one version value is live). Not an SEO surface per
  se, but it rides along with site-wide chrome edits — flag it if the change
  touches shared CSS/JS.

## New-page checklist (all mandatory) — the SEO subset

When the change is "add a page", the preflight's propagation steps should cover:

1. Self-referential extensionless `<link rel="canonical">`.
2. A `/<path>.html  /<path>  301!` line in `_redirects`.
3. `python _generate_sitemap.py --apply` (plus a `PAGE_META` entry for a new root
   page).
4. For a new **episode**: also `_validate_episode.py`, the real YouTube
   `maxresdefault.jpg` for og:image, and — after prod deploy — the IndexNow ping.
