# Canonicalization — verified state (2026-06-11)

Reference note for sessions building content / links / syndication on top of
Signal Room's canonical URLs. **The canonicalization gate is satisfied on
production.** Canonical URLs are stable; you can rely on them.

## Canonical rules
- **Host:** apex `signalroompodcast.com` — non-www, https. www is a Netlify
  domain alias that 301s to the apex.
- **URL form:** extensionless (`/episodes/foo`, never `/episodes/foo.html`).
- **Articles:** canonical URL is lowercase `/articles/...` even though the files
  live under `/Articles/` (capital A) on disk; `_redirects` handles the case
  rewrite + 301s.

## Live verification (curl against production, 2026-06-11)
| Request | Result |
|---|---|
| `https://www.signalroompodcast.com/` | 301 → `https://signalroompodcast.com/` (single hop) |
| `http://signalroompodcast.com/` | 301 → `https://signalroompodcast.com/` |
| `https://signalroompodcast.com/` | 200 (canonical destination) |
| `…/episodes/data-readiness-ai-adoption.html` | 301 → `…/episodes/data-readiness-ai-adoption` |
| `…/episodes/data-readiness-ai-adoption` | 200 |
| All variants followed with `curl -L` | terminate at a clean 200 apex extensionless URL |

- Self-referential `<link rel="canonical">` on every published page (52/52);
  all values `https://signalroompodcast.com/…` extensionless, lowercase
  `/articles/`. Confirmed rendering live, not just in the repo.
- `og:url` and JSON-LD `url` surfaces match the canonical (no www, no `.html`).
- Internal links carry no redirect hops: zero `.html`, `www.signalroom`,
  renamed-slug, or capital `/Articles/` internal links across `<a href>`.
- `sitemap.xml`: 51 locs, all clean apex extensionless.
- `404.html` is intentionally exempt from self-canonical + redirect rules.

## Known residual (inherent — do not try to "fix" in config)
Two-hop chains for www-host entry points only:
`http://www → https://www → apex` and `www + .html → apex + .html → apex
extensionless`. Netlify's TLS-edge scheme upgrade and the domain-alias→primary
redirect fire before `_redirects` path rules on the non-primary host, so these
cannot be collapsed to one hop via config. The final destination is always the
clean apex 200, and the ~17 www referring domains consolidate via the single
www-root→apex 301 — equity is not stranded.

## If you add a new page
Add a matching `/path/foo.html  /path/foo  301!` line to `_redirects`, give the
page a self-referential extensionless canonical, and add an extensionless `<loc>`
to `sitemap.xml`. (See the signal-room-site skill, "Canonical URL form" section.)

## Note on the Ahrefs flags that prompted this
The Ahrefs evidence (www UR 0 / empty title; `.html` duplicates UR 0) was a
**stale crawl** predating the 2026-05-21 extensionless flip + www alias. A
redirecting URL correctly shows UR 0 / no title because its equity has flowed to
the 301 target — that is the healthy post-fix state. Trigger an Ahrefs re-crawl
of project 9612773 to clear the flags.
