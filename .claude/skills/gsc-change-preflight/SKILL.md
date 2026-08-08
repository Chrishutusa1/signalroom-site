---
name: gsc-change-preflight
description: >-
  Mandatory pre-flight gate for The Signal Room site (signalroompodcast.com)
  that MUST run BEFORE any SEO-surface change is written or shipped. SEO is this
  site's job #1, and these surfaces silently control indexing and rankings, so
  invoke this skill whenever a task touches — or might touch — a canonical/OG
  URL, the `_redirects` file, `sitemap.xml`, a page `<title>` or
  `<meta name="description">`, `robots.txt`, the IndexNow key file, or sends an
  indexing request (IndexNow / "ping Google" / "request re-crawl" / "get this
  indexed"). Trigger it even when the user only says "add a page", "rename a
  URL", "redirect X to Y", "fix the meta description", "update the sitemap",
  "change the canonical", "deindex this", or "the page dropped in Search
  Console" — the SEO surface is implicit in all of those. When unsure whether a
  change is SEO-touching, run the preflight anyway; it is cheap and the cost of
  skipping it (a deindexed or mis-canonicalized URL) is not.
---

# GSC Change Preflight — The Signal Room

## Why this exists

SEO is this site's number-one job, and the surfaces that control it — canonical
tags, `_redirects`, `sitemap.xml`, titles/metas, `robots.txt`, indexing pings —
are **quiet**. A wrong canonical, a redirect that changes a URL Google already
ranks, or a stray `robots.txt` line does not throw an error, does not fail a
build, and often looks fine in the browser. The damage shows up weeks later as
lost impressions in Google Search Console (GSC), by which point the cause is
hard to trace and the recovery is slow.

This preflight is the gate that makes those changes **deliberate and
reversible**. It does three things before you touch anything:

1. **Captures the current state** of the affected URL(s) — what Google indexes
   and ranks today — so you know what you're putting at risk and can prove
   whether the change helped or hurt.
2. **Checks the change against the site's hard conventions** so it can't violate
   the canonical/redirect/sitemap/meta contracts.
3. **Emits a go / no-go verdict plus the exact propagation steps** the change
   requires downstream (sitemap regen, `_redirects` line, IndexNow ping).

Run it, produce the report, and only then make the change. If the verdict is
NO-GO, surface the blocker to the user rather than shipping.

## Step 0 — Classify the change

Name every SEO surface the task touches. A single task often touches several
(adding a page touches canonical + `_redirects` + `sitemap.xml`). Use this map:

| Surface | You're touching it when… | Hard convention (see `references/conventions.md`) |
|---|---|---|
| **Canonical / OG URL** | editing `rel="canonical"`, `og:url`, adding a page | apex host, https, extensionless, self-referential |
| **`_redirects`** | adding/renaming/removing a URL, any 301 | append-only; `pattern  target  301!` shape; no loops |
| **`sitemap.xml`** | adding/removing/renaming any page | generated only by `_generate_sitemap.py`; never hand-edit |
| **`<title>` / `<meta name="description">`** | rewording either | title ≤ 57 chars; description ≤ 155 chars |
| **`robots.txt`** | any edit | almost never changes; treat as high-risk |
| **IndexNow key file** | any edit to `*.txt` key at root | public by design; never move/rename/delete |
| **Indexing request** | IndexNow ping, "get this crawled/indexed" | deploy-time step, prod URLs only |

If the task touches **none** of these, this skill does not apply — say so and
proceed normally. If it touches **any**, continue.

## Step 1 — Capture the current GSC / index state

For every URL the change will alter, redirect, or remove, capture what it's
worth **today**, before you change it. This is the reversibility anchor: if the
change later costs traffic, this snapshot is how you notice and revert.

**Preferred — Google Search Console data via the Ahrefs MCP** (the site is
connected as an Ahrefs project). Pull the affected page's recent performance:

- `gsc-pages` / `gsc-page-history` — clicks & impressions for the exact URL.
- `gsc-keywords` / `gsc-keyword-history` — the queries the URL ranks for, so you
  know what a canonical/redirect change could disrupt.

Record, per URL: current clicks, impressions, and the top few ranking queries.
A URL with real impressions is **high-stakes** — changing its canonical or
redirecting it can forfeit that traffic, so the bar for proceeding is higher and
the user should confirm.

**If GSC/Ahrefs tooling is not connected in this session**, do not block on it —
degrade gracefully and note it in the report:
- Confirm the URL's live status directly: `curl -sI https://signalroompodcast.com/<path>`
  and check the HTTP status + any existing redirect.
- State plainly in the report that GSC data was unavailable and the traffic risk
  could not be quantified, so the user is deciding without it.

**New pages** have no history to protect — note "new URL, no current index
state" and move on; the risk there is misconfiguration, not lost traffic.

## Step 2 — Convention & integrity checks

Run the checks for each surface in scope. These are mechanical and mostly
scriptable — prefer running the repo's own tooling over eyeballing, because the
scripts encode the exact gates CI enforces.

### Canonical / OG URL
- Canonical is **self-referential**, **apex** (`signalroompodcast.com`, never
  `www`), **https**, and **extensionless** (`/episodes/foo`, not `/episodes/foo.html`).
- Articles are lowercase `/articles/...` in URLs even though files live in
  `Articles/` on disk — never emit `href="/Articles/..."`.
- `og:url` matches the canonical.

### `_redirects`
- The change is **append-only** — you're adding a line, not rewriting existing
  ones. Each line is `pattern  target  301!`.
- New page ⇒ there is a `/<path>.html  /<path>  301!` line.
- Trace the new line against existing rules for a **loop or shadow** (does the
  target itself match an earlier pattern?). A bad line can 404 or loop the site.

### `sitemap.xml`
- Never hand-edited. After the content change, regenerate and verify clean:
  ```bash
  python _generate_sitemap.py --check    # exit 1 if stale — this is the CI gate
  python _generate_sitemap.py --apply    # regenerate (lastmod preserved)
  ```
- A brand-new **root** page also needs a curated changefreq/priority entry in the
  script's `PAGE_META` before it will generate correctly.

### `<title>` / `<meta name="description">`
- For an episode page, the repo's validator is the source of truth:
  ```bash
  python _validate_episode.py episodes/<slug>.html        # title ≤57, meta ≤155, shorts alt
  python _validate_episode.py episodes/<slug>.html --fix  # word-trim meta, backfill alt
  ```
- For non-episode pages, check the two limits by hand: **title ≤ 57**,
  **description ≤ 155** characters. Over the limit is a hard fail.

### `robots.txt` / IndexNow key file
- Treat any edit as high-risk and confirm intent with the user. The IndexNow key
  file (`*.txt` at root) is **public by design** — never move, rename, or delete
  it.

### Indexing request (IndexNow)
- Only ping **production** URLs (`https://signalroompodcast.com/...`), and only
  **after** the change has merged to `main` and reached prod — pinging a URL
  whose new content isn't live yet just makes Google re-crawl the old version.
- Submit with the repo script (dry-run first):
  ```bash
  python signalroom-publish-normalize.py --indexnow --url https://signalroompodcast.com/<path> --apply
  ```
  Expect HTTP 200/202.

## Step 3 — Verdict & propagation checklist

Close with an explicit verdict and the ordered downstream steps. Emit the report
in this shape:

```
## GSC Change Preflight — <short description of change>

**Surfaces touched:** <list from Step 0>

**Current index state:**
- <url> — <clicks/impressions + top queries, or "GSC unavailable", or "new URL">

**Convention checks:**
- <surface>: PASS / FAIL — <one line of evidence>
- …

**Verdict:** GO / NO-GO / GO-WITH-CONFIRMATION
<if NO-GO or needs confirmation: the specific blocker and what the user must decide>

**Propagation steps (in order):**
1. <e.g. add _redirects line `/x.html  /x  301!`>
2. <e.g. python _generate_sitemap.py --apply>
3. <e.g. after merge reaches prod: IndexNow ping for the changed URL(s)>
```

**Verdict rules:**
- **NO-GO** if any convention check fails (over-length meta, hand-edited
  sitemap, malformed/looping redirect, non-apex or non-self-referential
  canonical). Fix the change, don't ship the violation.
- **GO-WITH-CONFIRMATION** if a checked convention passes but the change alters
  or redirects a URL that currently earns real GSC impressions, or touches
  `robots.txt` / the IndexNow key file. The mechanics are fine; the user needs
  to accept the traffic risk.
- **GO** if all checks pass and there's no meaningful traffic at risk (typically
  new pages, or body-only changes that don't move a canonical/redirect).

## The golden rule

The whole point is that SEO surfaces fail **silently and late**. When in doubt,
run the preflight and write the report — it is cheap, and it converts an
invisible, deferred risk into a visible, present decision the user can own.

See `references/conventions.md` for the full canonical/redirect/sitemap/meta
contracts and the deploy-flow context these checks assume.
