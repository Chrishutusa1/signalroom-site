# GAPS.md — honest audit of weaknesses (2026-07-12)

Ordered by severity, most important first. Each item: what / where / why it matters / a fix scoped small enough for a single session. All claims below were verified against the working tree on 2026-07-12.

---

## 1. Four load-bearing publish scripts are untracked (exist only on this one PC)

**What:** `.gitignore` line `/*.py` excepts only `_generate_topic_cards.py` and `signalroom-airtable-bridge.py`. That leaves **`_validate_episode.py` (the publish gate), `signalroom-publish-normalize.py` (alt-fix + IndexNow), `_update_stats.py`, and `_update_featured_guests.py`** untracked (`git status --ignored` confirms all four as ignored).
**Where:** `.gitignore` lines 11–14; the four scripts at repo root.
**Why it matters:** A disk failure, machine swap, or any cloud/worktree checkout silently loses the entire publish-gate tooling. The `signal-room-site` skill and memory notes instruct sessions to *run* these scripts — in a fresh clone they simply won't exist and a less capable model may conclude "no gate exists" and publish unvalidated pages.
**Fix (single task):** Add four `!` exception lines to `.gitignore` (`!/_validate_episode.py`, `!/signalroom-publish-normalize.py`, `!/_update_stats.py`, `!/_update_featured_guests.py`), `git add` the four files, commit. No code changes needed.

## 2. No CI and no automated enforcement of the publish gates

**What:** There are no tests, no GitHub Actions, nothing that runs `_validate_episode.py` automatically. The gates (meta ≤155, title ≤57, shorts alt) rely on a human/AI remembering to run a local script. Git history proves the failure mode is real: commits `359da6a` and `4a9925a` are both after-the-fact fixes of over-length metas that had already been merged.
**Where:** absent `.github/workflows/`; gates in `_validate_episode.py`.
**Why it matters:** The most frequent recurring defect class in this repo (meta/title/alt violations) has no automated backstop, and the cloud routine that creates episodes is known to emit one of the defects (empty alts).
**Fix (single task):** After fixing gap #1, add `.github/workflows/validate.yml` that on push/PR runs `python _validate_episode.py` over every file in `episodes/` (loop in bash; the script takes one path at a time) plus `python signalroom-publish-normalize.py --fix-alt` in dry-run and fails if it reports anything to fix.

**FIXED 2026-07-12:** `.github/workflows/validate.yml` added (episode gates, alt-normalize dry-run, single-CSS-version check, `_redirects` line-shape check). **KNOWN RED:** 17 pre-existing episode pages fail the title/meta gates (mostly titles 58–61 chars; EP35 at title 74 / meta 294) — the job stays red until those are trimmed. That trim is editorial SEO-surface work: run `gsc-change-preflight`, get Chris's sign-off on reworded titles.

## 3. Production deploys are manual directory pushes that can diverge from git

**What:** Prod is published with `netlify deploy --prod --site=98c71b47-cb1e-4eb2-8255-963349df8ccf --dir=.` from whatever is currently on this machine's disk; only staging tracks `origin/main`.
**Where:** deploy model documented in `signalroom-publish-normalize.py` docstring and `.claude/finalize_ep27.py`.
**Why it matters:** Uncommitted local edits ship to prod; conversely, merged commits don't go live until someone remembers to deploy. There is no record of exactly what prod is running. A session diagnosing "why doesn't prod show X" must always compare live HTML against the repo, not trust git.
**Fix (single task, low-risk):** Add a pre-deploy check script (`_predeploy_check.py`) that fails if `git status --porcelain` is non-empty or HEAD ≠ `origin/main`, and document in CLAUDE.md that it must pass before `netlify deploy --prod`. (Switching prod to git-driven deploys is the real cure but is an infrastructure decision for Chris, not a code task.)

## 4. Three different CSS cache-bust versions are live across pages

**What:** `style.css?v=` appears in three variants: `20260422r3` (30 pages), `20260628shorts2` (16 pages), `20260628shorts3` (10 pages). With `/css/*` cached 1 year immutable, pages pinned to an old `?v=` can serve stale CSS to returning visitors after any stylesheet change, and the split proves version bumps have been applied inconsistently.
**Where:** every `*.html`, `episodes/*.html`, `topics/*.html`, `Articles/*.html` `<link rel="stylesheet">`; caching rules in `netlify.toml`.
**Why it matters:** A future CSS change bumped on only some pages produces mixed styling that is invisible in local testing (no cache) and maddening to debug in prod.
**Fix (single task):** One sed/Python pass normalizing every `style.css?v=...` reference to a single current value (e.g. `v=20260712`), commit. Add a one-line checker to the CI job from gap #2 (`grep -rho 'style.css?v=[^"]*' --include='*.html' . | sort -u | wc -l` must equal 1).

**FIXED 2026-07-12:** all 57 pages normalized to `v=20260712`; single-version check enforced in `.github/workflows/validate.yml`.

## 5. `js/linkedin-links.js` guest map is stale (25 names vs 31+ guests)

**What:** The hardcoded name→LinkedIn map stops at roughly EP25-era guests (25 entries). Newer guests (e.g. Bennett Borden EP32, Dr Ömer Atlı EP33, Aaron Puckett EP34, Katherine Tuominen, Sid Dutta) are absent, so their cards on `guests.html` render without the LinkedIn icon while older guests get one — a visible inconsistency on a page whose whole point is showcasing guests.
**Where:** `js/linkedin-links.js` (loaded by `guests.html`, `index.html`, `Articles/*`). Episode pages are unaffected (they hardcode sidebar links).
**Why it matters:** Guest-relations optics; guests notice. Also nothing in the publish flow reminds anyone to update this file.
**Fix (single task):** For each guest card in `guests.html` lacking a map entry, pull the LinkedIn URL from the guest's own episode page sidebar (`sidebar-guest-linkedin` href) and add it to the map. Add "update js/linkedin-links.js" to the new-episode checklist in CLAUDE.md. (Better long-term: generate the map from episode pages the way `_generate_topic_cards.py` works.)

## 6. Duplicated shorts-alt fixing logic in two scripts

**What:** `_validate_episode.py --fix` and `signalroom-publish-normalize.py --fix-alt` both implement filling shorts-thumbnail `alt` from `data-short-title`, with *different* regexes and different semantics (the validator also replaces wrong non-empty alts and injects missing attributes; normalize only ever fills `alt=""`).
**Where:** `_validate_episode.py` lines 59–76; `signalroom-publish-normalize.py` lines 72–124.
**Why it matters:** Two implementations of the same guard will drift; a future template change could pass one and fail the other, producing confusing "gate says PASS but normalize wants changes" states.
**Fix (single task):** Make `_validate_episode.py` import/replicate exactly the normalize behavior for the alt check (or have it shell out to `signalroom-publish-normalize.py --fix-alt` for the fix path), and note in both docstrings which one is authoritative (normalize, since it also runs in the cloud flow).

## 7. Regex-driven generators are brittle to harmless-looking HTML edits

**What:** All maintenance scripts parse HTML with regexes anchored to exact formatting:
- `_update_featured_guests.py` hard-fails (`SystemExit`) if `<div class="guests-grid">...(</div>\s*</div>\s*</section>)` doesn't match `index.html` exactly once.
- `_update_stats.py` rewrites `id="episode-count">N<` and the phrases `See All N Episodes` / `N episodes published to date` / `N healthcare AI practitioners` — copy edits to those sentences break the sync silently (`n=0` substitutions are printed but nothing fails).
- `_generate_topic_cards.py` extracts guest names via `"@type":\s*"Person"[^}]*?"name"` — reordering JSON-LD keys breaks it.
- `_validate_episode.py` only matches `<meta name="description" content="...">` with that exact attribute order.
**Where:** the four scripts named above.
**Why it matters:** The most likely editor of these HTML files is a smaller model doing a copy tweak, which is exactly the actor least likely to know the markup doubles as a machine interface.
**Fix (single task):** Make the silent cases loud: in `_update_stats.py`, exit non-zero if any `re.subn` count is 0; in `_generate_topic_cards.py`, the WARNING-and-skip on incomplete JSON-LD should become a hard failure when `--apply` is passed. (Documenting the fragile patterns in CLAUDE.md — done — is the other half.)

## 8. `sitemap.xml` is fully manual and already missing one page

**What:** The `/articles/` index hub (added in HEAD commit `12a7457`) is not in `sitemap.xml` (54 locs; both article pages present, index absent). All episode pages are present today, but only because each publish flow remembered.
**Where:** `sitemap.xml`; new-page checklist in `CANONICALIZATION-VERIFIED.md`.
**Why it matters:** Manual sitemap + manual redirects + manual canonical = three chances to forget per new page. The repo's own history (`_redirects` "legacy sitemap slugs (404 ghost URLs)" block) shows sitemap drift has caused indexing junk before.
**Fix (single task):** Add `<url><loc>https://signalroompodcast.com/articles/</loc>...</url>` now. Then (separate task) write `_generate_sitemap.py` that derives the sitemap from the files on disk + a small exclusion list, using each file's git last-commit date for `<lastmod>`; run it in the publish flow. **Caution:** any sitemap change is an SEO surface — the `gsc-change-preflight` skill applies.

## 9. Historical one-shot scripts are tracked; current worktree/branch litter

**What:** `.claude/finalize_ep27.py` (EP27 shipped in April) and `.claude/rollout_perf_edits.py` (rollout completed — every page now has the deferred GA loader) are dead code, but `finalize_ep27.py` is also the only in-repo record of the prod site ID. Additionally `.claude/worktrees/` contains three stale worktrees (`dazzling-curie`, `festive-mendel`, `nervous-williams` — the last on an unmerged local branch), and local branches `claude/*`, `fix/episode-shorts-alt` plus remote branches `Chrishutusa1-patch-1/2`, `seo/canonicalization-hardening`, etc. linger.
**Where:** `.claude/`, `.claude/worktrees/`, `git branch -a`.
**Why it matters:** Dead scripts get mistaken for current process by smaller models ("run finalize_ep27"); stale worktrees waste disk and confuse `grep -r`.
**Fix (single task):** Delete the two scripts after moving the site ID + deploy command into CLAUDE.md (done in this transfer); remove merged/stale worktrees with `git worktree remove`; delete local branches whose work is merged. Leave unmerged `claude/nervous-williams-1f1569` for Chris to review before deletion.

## 10. Guest-application function: minor robustness/security notes (severity: low)

**What:** `netlify/functions/submission-created.js`:
- No length caps on any field except `User Agent` (500); a hostile submission can push multi-KB strings into Airtable and into the notification webhook.
- The auto-reply emails whatever address the submitter typed, using template text — an open (if weak) vector for sending Signal-Room-branded mail to arbitrary addresses. Honeypot is the only bot control.
- `typecast: true` on the Airtable write lets Airtable coerce/create select options from user input.
- Secrets handling is correct (env vars, none in repo). The committed `1577c9c65cc397ca183ed80f92e0f9cf.txt` IndexNow key is public **by design** — not a leak.
**Where:** `netlify/functions/submission-created.js`.
**Why it matters:** Spam/abuse annoyance and Airtable data hygiene rather than a real breach risk; there is no PII exposure beyond what the submitter provides.
**Fix (single task):** Add a `clip = (s, n=1000) => String(s ?? "").slice(0, n)` applied to every field, and skip the auto-reply when the honeypot field is present or the email fails a trivial format check. Keep the always-200 contract.

## 11. Inconsistencies (cosmetic-to-minor, batchable)

- **Favicon MIME mismatch:** every page declares `<link rel="icon" href=".../Signal_Room_Cover_FINAL_v2.png" type="image/jpeg">` — a PNG labeled `image/jpeg`. Browsers sniff past it; still wrong. Fix: site-wide replace to `type="image/png"`.
- **Inline styles vs stylesheet:** episode-page bodies rely heavily on inline `style=""` (colors hardcoded, e.g. `#6c63ff` vs the palette's `--purple-primary: #6C5CE7`), while chrome uses CSS variables. Cosmetic drift; don't "clean it up" wholesale (the markup doubles as script interface — gap #7), but new pages should prefer the variables.
- **`meta name="keywords"`** on `index.html` — obsolete, ignored by engines; harmless. Remove on next homepage touch.
- **`_redirects` alignment drift** at lines 102–103 (the two newest episode lines break the column alignment) — pure cosmetics, but it signals the file is appended to under time pressure; a malformed future append is the real risk. The CI check in #2 could validate `_redirects` line shape (`^\S+\s+\S+\s+(200|301!?)$`).
- **`data/*.csv`** are stale point-in-time exports (March–April 2026) that nothing consumes at runtime. Fine to keep; do not treat as current data.

## 12. Single-machine bus factor beyond the repo

**What:** The publish flow depends on assets that live only outside this repo: the claude.ai "add-podcast-episode" and shorts-injection cloud routines, secrets in `C:\Users\PC\Desktop\HDSC\SignalRoom\.env`, guest photos in `...\SignalRoom\GuestData\`, and Netlify/Airtable credentials. None are documented here beyond docstrings.
**Why it matters:** This repo alone cannot reproduce the pipeline; a new operator (human or AI) needs the `signal-room-site` skill and Chris's accounts.
**Fix (single task):** Nothing to code — the dependency map is now written down in PROJECT.md §Architecture. Keep it current when the cloud routines change.
