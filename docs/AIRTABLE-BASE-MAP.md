# Airtable Base Map — "Content Intelligence Hub" (`app3hF8k8ZGXvf9XF`)

Full inventory of the Signal Room / HDSC content-operations base: **70 tables** grouped by
function. Read live from the base schema this session. This is the data backbone the
`CONTENT-OPS-PIPELINE.md` and `AUTOMATION-INVENTORY.md` docs sit on top of.

> IDs are stable; names may drift. Operate on IDs. "★" marks tables central to the episode
> pipeline.

---

## Podcast / episodes
| Table | ID | Purpose |
|---|---|---|
| ★ Podcast Episodes | `tblzKDGrxDnhFqQUU` | Master episode catalog — Buzzsprout + YouTube IDs/URLs, tags, show notes, plays/views stats, guest headshot |
| ★ Buzzsprout Episode Data | `tblrji2ivwJQYE6Rg` | Buzzsprout-side record — `Buzzsprout Status`, `Transcript Source`, episode metadata |
| YouTube Shorts | `tblan7fxvxW0kpti2` | Short clips cut from episodes; tags + view metrics |
| Episode QA Punch List | `tblj7rmr8rysMf3q5` | Per-episode QA checklist |
| Show Stats | `tblXfU1hpEdSbMOHH` | Aggregate show metrics snapshots (plays, views, subs, reach) |
| Platform Stats | `tblN5LPivxwA9cuLA` | Per-platform daily stats (the `podcast-stats-cloud` target) |
| Podcast Snapshots | `tblPEMGCn2oBg8rzV` | Point-in-time podcast metric snapshots |
| Reviews | `tblAOOseTDP4UwDRe` | Podcast reviews |

## Guests & inbound (pipeline front-door)
| Table | ID | Purpose |
|---|---|---|
| ★ Guest Opportunities | `tbl7BjmotGvcUtVa4` | Inbound opportunity engine — fit-scored, 15-state machine, Outlook-linked |
| ★ Guest Applications | `tbloZMd3IzXNo20jY` | Guest prep intake — `Status` New→Reviewing→Scheduled→Recorded |
| Inbox Triage | `tblvUsmT5UMpXOCoL` | Email triage + domain enrichment (Ahrefs DR/metrics, SR Guest Request flag) |
| Email Messages | `tblt8QJyoPqkcOsid` | Outlook message mirror + AI classification |
| Email Threads | `tbljL3RRRxDtjhINW` | Outlook conversations grouped |
| Status Events | `tbldtNaIt4CihWRVC` | Audit log of opportunity status transitions |
| Media Queries | `tbldlVB349hjIHcZU` | Inbound media/PR queries |
| Leads | `tbl8O3S6cYSeOxGHr` | Lead records |
| Speaking & Appearances | `tbly5ejCAblDMmSFW` | Speaking engagements |
| Press Mentions | `tblYCvc2VzTUkig1y` | Press/media mentions |
| Byline Pitch Pipeline | `tblNAHiBg3sz3gu1u` | Guest-byline / article pitch tracking |

## Newsletter — AI Health Pulse (Beehiiv)
| Table | ID | Purpose |
|---|---|---|
| Newsletter Issues | `tblpRSTOIr5io9bHD` | Issue catalog — Beehiiv/LinkedIn/Substack URLs, body, open/click rates |
| Subscribers | `tblm2tV9rLPZFHARH` | Beehiiv subscriber mirror (UTM, role, status) |
| Mirror Health | `tblKmfmiMfQKtuvOD` | Beehiiv↔Airtable divergence check |
| Newsletter Snapshots (BeeHiiv) | `tblLtatXN1QJarCWO` | Newsletter metric snapshots |

## Content / social / LinkedIn
| Table | ID | Purpose |
|---|---|---|
| LinkedIn Post Intelligence | `tbl7MyL2Y7pKBiL1l` | LinkedIn post performance + optimization scoring (AuthoredUp) |
| Content Calendar | `tbl6YoHeYCXD1u73d` | Planned post slots + briefs |
| Content Cross-Links | `tblKtlmXCpBwsk4qC` | Internal cross-linking ledger |
| Content Index | `tblKCkHE2p1ujsgfo` | Master content index |
| Content Targeting Queue | `tbl6TCyOL74ui6hCE` | Content-gap → target queue |
| HDSC Insights | `tblNL2Wr0egrp0V8v` | Insight snippets reused across content |
| SR Promo Quote Candidates | `tblvoXu82nPffsheh` | Pull-quote candidates for promo |
| SR Cross-Promo Collaborators | `tblFJD1b7ZdjwA0aV` | Cross-promo partner tracking |

## SEO / keyword intelligence (PhraseIntel family)
| Table | ID | Purpose |
|---|---|---|
| PhraseIntel Top 200 | `tblG996rZHtZnGaNa` | Master keyword intelligence (Ahrefs + Ubersuggest + AI-channel scores) |
| PhraseIntel Snapshots | `tbl4cVIo3aaRnRmEE` | Time-series of Top 200 |
| PhraseIntel SR Top / SR Snapshots | `tbltwiuTJPTlI5F2Y` / `tblhMUMqSaZJfobz8` | Signal-Room-specific keyword set + history |
| PhraseIntel CJH Top / CJH Snapshots | `tblTI9C9Z0tvwEDZe` / `tblLyIu31Jcbm8jRe` | Chris Hutchins personal-brand keyword set + history |
| PhraseIntel PodcastPull Top / Snapshots | `tblH5CgNgMQB4jcL0` / `tblE7VzBFmzB5OJC2` | Podcast-pull keyword set + history |
| PhraseIntel — Mention Share | `tblyaLswmOgvG5O71` | Share-of-voice / mention share |
| Organic Keyword Pool (PodSEO) | `tblpLts7u1VvacIWh` | Podcast-directory keyword pool |
| PodSEO Rankings | `tblodMRdNs7Z6mtAI` | Apple/Spotify/Amazon/YouTube podcast search ranks |
| Pivot Alerts | `tbljgWOxUHLmB4ek7` | Rank/keyword pivot alerts |

## Rankings & analytics snapshots (external tools)
| Table | ID | Purpose |
|---|---|---|
| Ubersuggest Rankings | `tbljgURzI9xYENVS5` | Ubersuggest keyword ranks |
| SEO Snapshots (Ubersuggest) | `tbl94AiVskrGUcxff` | Ubersuggest site snapshots |
| SEO Snapshots (Ahrefs) | `tblpjJfQnpCXDRofc` | Ahrefs site snapshots |
| SEO Snapshots (Similarweb) | `tbldEXABBZcznxJ4U` | Similarweb snapshots |
| AEO Snapshots (Otterly) | `tblCTvKBoP8n9zmqh` | OtterlyAI answer-engine visibility |
| GSC Snapshots | `tblngLbX2HUD8MlXV` | Google Search Console snapshots |
| GSC Regression State | `tblNFWBPtGEgNJXrt` | GSC regression detector state |
| Google Snapshots | `tblqxPP7q9crE2Bpq` | Google SERP snapshots |
| Traffic Snapshots | `tbllHqrejuZpcpfwc` | Traffic snapshots |
| GA4 Cross-Site Snapshots | `tblmyJ3wLHFyiCYqJ` | GA4 across owned properties |
| Visitor Growth Intel Snapshots | `tbl9uMIx5SO51K7r9` | Visitor-growth intelligence |
| Reach Log | `tblh9MSaxTIPIB9X5` | Combined-reach log |

## Backlinks / off-page
| Table | ID | Purpose |
|---|---|---|
| AEO Off-Page Targets | `tblUjpeqQW9nU78Ne` | Off-page authority targets |
| Disavow Ledger | `tblN81NIPpu70pT2H` | Backlink disavow list |

## Web properties & ecosystem
| Table | ID | Purpose |
|---|---|---|
| Web Properties | `tblUJdMWoQk3prH0a` | Owned domains/properties registry |
| Ecosystem Products | `tbldXIctNGgQ4kISt` | Product catalog across the ecosystem |
| Ecosystem Discounts | `tblQJFMUmGNylfw8L` | Partner/product discount codes |

## Ops / infra / governance
| Table | ID | Purpose |
|---|---|---|
| ★ Operations Registry | `tbll4LJ0OPAXHdkkw` | Scheduled-task catalog (mirror of `scheduled-tasks.json`) — cron, enabled, last run |
| Schedule Heartbeats | `tblUmY97D6GxFFERY` | Per-run execution log (fired-at, status, duration, run ID) |
| Strategic Projects | `tblveLV5K6VEZKrOH` | Project tracker |
| Credential Inventory | `tblQtQjrJkbk2GuEk` | Credential/asset inventory |
| API Keys | `tbldkMjFsrBSHO76q` | Master credentials (secrets — handle with care) |

## Client / other
| Table | ID | Purpose |
|---|---|---|
| Richard Jones Video Transcripts | `tbl0fgivwn28E3et5` | Client transcript store |
| Richard Jones Transcript Chunks | `tblUgHCk9bqIP3e8a` | Chunked transcripts for retrieval |

## Archived (inactive)
| Table | ID |
|---|---|
| _archived_FeedIntelligence_2026-04-28 | `tbl8JX3GgCnmyGqaS` |
| _archived_CombinedInbox_2026-04-28 | `tbl7LcIRDb0XkcGas` |

---

## What the map tells us

- The base is a **full content-operations warehouse**, not just a podcast tracker — SEO/AEO
  intelligence, newsletter, LinkedIn, cross-brand (HDSC + client) analytics, and an ops/scheduler
  layer all live here. The podcast pipeline is one lane among many.
- **CLAUDE.md under-describes it.** The repo's notes mention a handful of tables; the base has 70,
  including the scheduler (Operations Registry / Schedule Heartbeats) and the full inbound
  guest engine — context worth surfacing before building new automation.
- **Everything is linked.** Podcast Episodes, Newsletter Issues, and the PhraseIntel sets are
  richly cross-linked, so the content pipeline can ground new work (show notes, social, SEO) in
  the existing corpus without AirOps.
