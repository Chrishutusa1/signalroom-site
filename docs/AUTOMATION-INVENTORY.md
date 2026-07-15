# The Signal Room — Automation Inventory & Inbound Pipeline

Companion to `CONTENT-OPS-PIPELINE.md`. Documents the **existing automation** discovered in the
Airtable *Content Intelligence Hub* base — the scheduled-task catalog, the inbound
guest-opportunity engine, and a cloud-readiness assessment against the "run it all in the cloud"
goal.

> Source: read live from base `app3hF8k8ZGXvf9XF` this session — the *Operations Registry*
> (`tbll4LJ0OPAXHdkkw`, ~50 tasks), *Schedule Heartbeats* (`tblUmY97D6GxFFERY`), and the
> guest-inbound tables. AirOps is out of scope.

---

## 1. How the scheduled automation works

- **Source of truth is a `scheduled-tasks.json` file** (per the `operations-registry-mirror`
  task: *"Mirrors scheduled-tasks.json into Operations Registry. Source-of-truth is the JSON,
  not this table."*). The Airtable *Operations Registry* is a **mirror** of that file for
  visibility — not the scheduler itself.
- **Execution:** a scheduler runs the JSON's cron entries. Each run writes a row to
  **Schedule Heartbeats** (Task ID, Fired At, Status, Duration, Run ID, Fire Source).
- **Self-monitoring:** `schedule-heartbeat-audit` (nightly) verifies every task fired in its
  window; `session-health-monitor` and `infrastructure-audit` watch scheduler/OAuth/vendor health.
- **~50 tasks total: ~27 Active, ~23 Disabled.**

### The critical constraint for "run in the cloud"

**Almost every task is LOCAL — it has a "computer-on" dependency.** Evidence: tasks write to
`C:/Users/PC/Desktop/...`, drive a local **Chrome MCP**, pull from **AuthoredUp**, and the git
repo path is `C:/Users/PC/Documents/GitHub/signalroom-site`. If that machine is off, they don't run.

**Only one task is truly cloud-native today:** `podcast-stats-cloud` — *"No computer-on
dependency (GitHub Actions cron)"*, running in the private repo
**`Chrishutusa1/signalroom-stats-pipeline`**. **This is the model to replicate** to move the rest
into the cloud.

---

## 2. Scheduled-task catalog (grouped)

### Episode pipeline (the publishing workflow)
| Task | Cadence | State | What it does |
|---|---|---|---|
| `episode-prep-check` | Tue 16:00 | **Active** | Pre-episode check: Buzzsprout + YouTube + Airtable metadata for the upcoming **Wed** episode |
| `episode-publish-cascade` | Wed 01:00 | **Active** | Post-publish cascade: site deploy + JSON-LD, **verify-only** (prod approval gate removed — prod auto-publishes, see §5) |
| `episode-publish-verify` | Wed 08:00 | **Active** | Verifies BZ + YT + site URLs all live and consistent |
| `add-podcast-episode` | Manual | Disabled | Builds the episode page on **staging** from Airtable (the "add-podcast-episode routine") |
| `signal-room-prod-sync` | — | **Retired** | Prod auto-publishes from `main`; no manual deploy step remains (see §5) |
| `signal-room-episode-sync-check` | Wed 09:03 | Disabled | Validates BZ/YT episode data vs *Podcast Episodes*, creates missing rows |

> Episodes drop **weekly on Wednesdays**. Prod go-live is **automatic** (auto-publish on merge to
> `main`); the cascade is now verify-only.

### Newsletter — AI Health Pulse (Beehiiv)
| Task | Cadence | State | What it does |
|---|---|---|---|
| `aihp-publish-cascade` | Mon 06:55 | **Active** | Prep Beehiiv send, **request approval, send on YES** (= the G3 draft-and-hold gate) |
| `aihp-publish-verify` | Mon 08:00 | **Active** | Post-publish Beehiiv + Airtable writeback consistency |
| `subscribers-pulse` | Daily 06:00 | **Active** | Beehiiv→Airtable subscriber mirror + net-change alert |
| `aihp-master-backup-weekly` | Sun 05:00 | **Active** | Weekly newsletter master-list backup |

### Content / social (LinkedIn)
| Task | Cadence | State | What it does |
|---|---|---|---|
| `content-calendar-planner` | Sun 16:00 | **Active** | Generates 5 optimized LinkedIn slots for the week |
| `linkedin-engagement-sync` | Daily 06:30 | **Active** | AuthoredUp pull into *LinkedIn Post Intelligence* |
| `linkedin-post-sync` | Daily 06:09 | Disabled | Superseded by engagement-sync |

### SEO / AEO / keyword intelligence
`phraseintel-refresh` (monthly), `phraseintel-pulse` (Mon), `phraseintel-pivot-watch` (daily),
`position-sweep` (Thu), `opportunity-scan` (Wed — SEO tag/cross-link/content gaps, **not** guest
opps), `aeo-authority-map-refresh` (Mon), `refdomain-audit` (monthly), `brand-alchemy-scan`
(daily), `airops-sync-watch` (daily) — mostly **Active**; a cluster of `prompt-*` approval-draft
tasks and `*-tag-optimizer` tasks are **Disabled**.

### Ops / infra / governance
`operations-registry-mirror` (daily 23:30), `schedule-heartbeat-audit` (nightly),
`session-health-monitor` (daily), `infrastructure-audit` (monthly), `strategic-review` (Fri),
`brand-rollup` + `vendor-review` (quarterly) — **Active**.

### Cross-brand / client (out of the podcast scope, listed for completeness)
`weekly-seo-health-check` (HDSC), `hdsc-moat-keyword-monitor`, `client0-paih-site-monitor`,
`wikidata-account-hygiene-weekly` — **Disabled**.

---

## 3. The inbound guest-opportunity engine (email → opportunity)

This is the "existing inbound automation" inferred from the machine states. It is **event-driven
off email, not a scheduled task** — it does not appear in the Operations Registry. The data flow,
reconstructed from the table schemas:

```
Outlook / Microsoft 365 inbox
   │  (Outlook Conversation ID · Message ID · Internet Message ID · Web Link carried throughout)
   ▼
Email Messages (tblt8QJyoPqkcOsid)      ← mirror of each message + AI Classification + Confidence
   ▼
Email Threads (tbljL3RRRxDtjhINW)       ← grouped by Outlook Conversation ID
   ▼
Inbox Triage (tblvUsmT5UMpXOCoL)        ← Category · Priority · Why It Matters · Suggested Next Step
                                           + SR Guest Request (checkbox) + Guest Domain
                                           + Audience/Followers + Domain DR + Ahrefs Site Metrics + Service Fit
   ▼
Guest Opportunities (tbl7BjmotGvcUtVa4) ← structured opportunity: Sender/Show, Proposed Topic,
                                           Fit Score, Confidence, Source Credibility, Evidence Summary,
                                           Risk Flags, Recommended Next Action, Human Review Required,
                                           Draft Status, Current Status (15-state machine)
   ▼
Status Events (tbldtNaIt4CihWRVC)       ← audit log of every transition (From→To, Reason, Changed By, Source)
```

**What the automation already does:** mirrors Outlook mail, AI-classifies each message, triages
it, **enriches the sender's domain with Ahrefs metrics (DR, site metrics)**, flags likely guest
requests, computes a **Fit Score + Confidence**, recommends a next action, and can pre-draft a
reply (`Draft Status`). A **`Human Review Required`** checkbox is the built-in gate.

**How this maps to the pipeline (`CONTENT-OPS-PIPELINE.md` §3):** this engine *is* **Stage 1 —
Guest Opportunity Assessment**, already largely built. The pipeline doc's Stage 1 should be read
as "formalize + cloud-host what already runs here," not "build from scratch."

**What's unconfirmed:** the *executor* of this email→opportunity flow (an Airtable automation, a
Microsoft-365-triggered Code session, or a local script) is not recorded in the Operations
Registry. Confirming and, if local, **cloud-hosting it** is the main open task for the inbound half.

---

## 4. Cloud-readiness assessment (against the "run in the cloud" goal)

| Lane | Today | To run in the cloud |
|---|---|---|
| **Podcast stats** | ✅ Cloud (GitHub Actions `signalroom-stats-pipeline`) | Already done — the template for everything else |
| **Episode publish** (prep/verify) | 🟢 Prod deploy **automatic** (auto-publish on merge); cloud verify via `episode-ops.yml`; page-build still agent+PR | Fill in the page-build port |
| **Inbound guest engine** | ⚠️ Event-driven, executor likely **local/desktop** | Host the Outlook→Opportunity flow in the cloud |
| **Newsletter (AIHP)** | ⚠️ Local | Port cascade/verify to cloud runners |
| **SEO/AEO + social** | ⚠️ Mostly local (Chrome MCP, AuthoredUp) | Hardest to port (browser-automation dependent) |
| **Self-monitoring** | ⚠️ Local | Port heartbeat-audit / infra-audit to cloud |

**Recommendation:** replicate the `podcast-stats-cloud` pattern — move `scheduled-tasks.json`
entries into **GitHub Actions cron** (or web Code-session Routines) lane by lane, starting with
the episode-publish and inbound-guest lanes since those are the pipeline spine. Keep the
Schedule-Heartbeats logging so the cloud runs remain observable.

---

## 5. Reconciliation — what today's work changed

**Production deploy is now fully automatic (decided 2026-07-15).** The prod site `signalroom` was
git-linked to `main` this session; the team then **dropped the manual prod gate** and enabled
**auto-publishing**, so every merge to `main` deploys to signalroompodcast.com automatically —
same as staging. This supersedes **both** the old Netlify Drop zip workflow **and** the interim
manual "Trigger deploy" gate. Consequences:

- **`signal-room-prod-sync` → RETIRED** in `scheduled-tasks.json` / Operations Registry. There is
  no manual prod deploy step anymore.
- **`episode-publish-cascade` → prod approval gate removed.** It becomes verify-only;
  `episode-publish-verify` confirms the auto-deploy landed (`commit_ref == main HEAD`).
- The error-prone local zip-drop is gone from the prod path — a direct win for the
  cloud/repeatability goal. The safety gate moves to **merge time** (PR + `validate.yml` CI +
  staging preview).
- Activating mechanism: the Netlify **`signalroom`** site → Build & deploy → Continuous
  deployment → production branch `main`, **"Stop auto publishing" = OFF**.

---

## 6. Open tasks

1. **Netlify:** confirm `signalroom` has auto-publishing **on** (Stop auto publishing = off) so
   merges to `main` deploy to prod.
2. Edit `scheduled-tasks.json` on the host: retire `signal-room-prod-sync`, drop the prod gate in
   `episode-publish-cascade` (see §5). The nightly `operations-registry-mirror` then self-heals
   the Airtable mirror.
3. Locate `scheduled-tasks.json` and confirm the executor/host (local machine vs cloud runner).
4. Confirm the inbound guest engine's executor; cloud-host it if local.
5. Port the remaining episode-publish + inbound lanes to the `podcast-stats-cloud` (GitHub
   Actions) model. (The verify lane is already ported — `episode-ops.yml`.)
