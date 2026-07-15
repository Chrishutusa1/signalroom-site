# The Signal Room — Content Operations Pipeline

End-to-end process for taking a healthcare-AI podcast guest from first contact through
a published, distributed episode on **signalroompodcast.com** — designed to run **in the
cloud** and be executed by **agents** with consistent, repeatable, verifiable steps.

> Status: **draft for review.** This documents the process as it actually runs today
> (reconstructed from the EP34/EP35 builds) plus the target cloud/multi-agent design.
> AirOps is intentionally **out of scope** (excluded from the ecosystem).

---

## 1. Systems of record (the ecosystem)

| System | Role in the pipeline | Key IDs |
|---|---|---|
| **Airtable — "Content Intelligence Hub"** | Pipeline database & single source of truth for guests + episode metadata | base `app3hF8k8ZGXvf9XF` · **Guest Opportunities** (inbound engine) `tbl7BjmotGvcUtVa4` · **Guest Applications** (prep intake) `tbloZMd3IzXNo20jY` · **Buzzsprout Episode Data** `tblrji2ivwJQYE6Rg` · Podcast Episodes `tblzKDGrxDnhFqQUU` · Credential Inventory `tblQtQjrJkbk2GuEk` · API Keys (master creds) `tbldkMjFsrBSHO76q` |
| **Google Drive — `GuestData/`** | Asset store: per-guest folder with headshot, bio, transcript | folder per `<Guest Name>` |
| **GitHub — `Chrishutusa1/signalroom-site`** | The website source of truth; PR-based changes | branch `main` |
| **Netlify — `signalroom-staging`** | Auto-deploys `main` → staging preview | site `75176784-…` (staging URL + PR deploy previews) |
| **Netlify — `signalroom`** | **Production** → signalroompodcast.com; Git-linked to `main`, deploy on trigger | site `98c71b47-…` |
| **Buzzsprout** | Podcast host / audio distribution | podcast `2550733` |
| **YouTube — @SignalRoomPodcast** | Video host; thumbnail is the canonical episode image | `img.youtube.com/vi/<ID>/maxresdefault.jpg` |
| **Beehiiv — "The AI Health Pulse"** | Newsletter distribution | embedded subscribe form |
| **Riverside FM** *(future)* | Recording + auto-transcript source | MCP pending |

**Not in the ecosystem:** AirOps (excluded). Content generation and grounding are done by
the executing agent using the Airtable records + Drive assets + the existing site as context.

---

## 2. Current automation inventory (what exists today)

Scanned this session:

- **Scheduled jobs (cron):** none.
- **GitHub Actions / workflows:** `validate.yml` (publish-gate CI on push/PR) and
  `episode-ops.yml` (scheduled episode prep/verify + prod-ready gate — the cloud port of the
  local episode lane; read-only v1). The external `signalroom-stats-pipeline` repo also runs a
  stats Action.
- **Deploy scripts in repo:** none (`netlify.toml` config only; `publish = "."`).
- **Routines / scheduled triggers:** could not be read (connector instability at scan time — see §7).
- **Evidence of existing (non-repo) automation:** the *Guest Opportunities* table carries
  machine states (`needs_dedupe`, `needs_enrichment`, `draft_created`) and the base has
  `Schedule Heartbeats` and `Status Events` tables — so an **inbound-intake automation already
  runs somewhere outside this repo** (Airtable automations / another Code session / external
  script). It just isn't versioned here and wasn't inventoried this session.
- **Net effect:** the *website-publishing* half (Stages 4–6) has **no scheduled automation** and
  is driven manually per session; the *inbound* half (Stage 1) appears partly automated already.
  Making the whole thing "run in the cloud" means (a) locating and documenting the existing
  intake automation, and (b) converting Stages 2–7 into scheduled/triggered agent runs (§6).

---

## 3. The pipeline (stage by stage)

Each stage names its **trigger**, the **agent work**, the **human gate**, and the
**system-of-record update** so any cloud session can execute it identically.

### Stage 1 — Guest Opportunity Assessment
- **Trigger:** new inbound row in *Guest Opportunities* (`tbl7BjmotGvcUtVa4`),
  `Current Status = new_unreviewed`.
- **Agent work:** dedupe → enrich (role, company, LinkedIn, healthcare-AI relevance) → classify
  (`Classification`) → score fit against ICP using prior episodes → set `Priority` and
  `Recommended Next Action`; optionally pre-draft a reply (`Draft Status = recommended`).
  This mirrors the existing machine states (`needs_dedupe → needs_enrichment → ready_for_review`).
- **System update:** `Current Status → strong_fit | conditional_fit | not_a_fit | hold_for_later`.
- **Human gate (G1):** host confirms the recommendation; approving a drafted reply moves
  `Draft Status → approved_to_create`; booking moves `Current Status → booking_in_progress → booked`.
- **Output:** a qualified, booked guest.

### Stage 2 — Guest Prep Review
- **Trigger:** guest accepted + recording scheduled.
- **Agent work:** gather bio + headshot + company from Drive `GuestData/<Guest>` and Airtable;
  fill gaps from the web; draft a **prep brief** (angle, 8–10 question outline, risk/verify
  notes — e.g. exact company/title); ensure the Drive guest folder exists and is populated.
- **System update:** prep brief saved to the guest's Drive folder + linked in *Guest
  Applications*; `Status → Reviewing`, then `Scheduled` once the recording is booked.
- **Human gate (G2):** host reviews/edits the prep brief before recording.

### Stage 3 — Record  *(future: Riverside FM MCP)*
- **Trigger:** recording completed in Riverside.
- **Agent work:** pull the recording + **auto-transcript** via the Riverside MCP; store the
  transcript in `GuestData/<Guest>` and attach to the Airtable episode record.
- **System update:** *Guest Applications* `Status → Recorded`; *Buzzsprout Episode Data*
  `Transcript Source → Third-Party Integration` (the field already anticipates this path).
- *Until Riverside MCP exists:* `Transcript Source = Manual Upload` and the transcript is added
  manually when supplied (Stage 5).

### Stage 4 — Publish to site (staging)
- **Trigger:** episode live on Buzzsprout + YouTube (or its scheduled go-live date).
- **Agent work — verify first, then build:**
  1. **Pull authoritative metadata from Airtable** (episode #, title, date, runtime,
     Buzzsprout ID) and the guest record (name, exact title/company, LinkedIn, bio, outline).
     *Never write copy from memory or ambiguous web search* — this is what caused the
     "Bedrock Security" → "Bedrock Data" correction on EP35.
  2. Build `episodes/<slug>.html` from the house template: title/meta/OG, YouTube embed
     (`youtube.com/embed/<ID>`), `og:image` = YouTube `maxresdefault`, info card, show notes
     (from the **real** outline), About + LinkedIn, Related Resources, and the three JSON-LD
     blocks (PodcastEpisode / FAQPage / BreadcrumbList).
  3. Add `assets/guests/<slug>.jpg` (400×400, head-and-shoulders — house standard).
  4. Wire into the site: `index.html` (cards + counts), `guests.html`, `episodes.html`,
     `sitemap.xml`. *(See §4 for the efficiency fix that collapses this into one checked step.)*
- **PR flow:** commit to `claude/…` branch → push → **draft PR** → verify Netlify deploy
  preview → mark ready → **squash-merge** to `main`.
- **System update:** merge to `main` **auto-deploys to staging**. *Buzzsprout Episode Data*
  `Buzzsprout Status` tracks the audio side (`Scheduled → Published`); the site-`staged` state
  lives in Netlify, not Airtable (see the `Site Status` recommendation in §8).

### Stage 5 — Transcript
- **Trigger:** transcript available (Stage 3 output, or supplied by host).
- **Agent work:** add the collapsible **"Full Episode Transcript"** `<details>` section
  (EP34/EP35 markup), lightly cleaned — fix show name + proper nouns, drop timestamps/stutters,
  one paragraph per speaker turn.
- **PR flow:** follow-up PR → squash-merge. *(With Riverside auto-transcript, fold this into
  the Stage 4 PR so there's one PR per episode — see §4.)*

### Stage 6 — Production deploy + validate
- **Trigger:** episode approved for prod go-live.
- **Agent work:** deploy `main` to the `signalroom` prod site (**Netlify → Deploys → Trigger
  deploy → Deploy site**, or push if auto-publish is on). Static deploy is **all-or-nothing**:
  it promotes all of current `main`, not one page.
- **Validate:** confirm the new prod deploy has **state `ready`**, **`commit_ref` == `main`
  HEAD**, **`build_id` present**, published today. (This is how deploy `4299bfb` was validated.)
- **System update:** site is live (Netlify); if the `Site Status` field is added (§8), set `live`.

### Stage 7 — Distribution & visibility
- **Trigger:** episode live on prod.
- **Agent work:** newsletter feature (Beehiiv), social posts (LinkedIn, YouTube community),
  internal notify (Slack); optional SEO/answer-engine check (Ahrefs/Ubersuggest connectors).
- **System update:** distribution status recorded in Airtable.

---

## 4. Scrutiny — efficiency & streamlining fixes

Improvements identified from the EP34/EP35 runs. These make the process faster *and* more
error-proof:

1. **Single source of truth = Airtable, always.** Generate page copy from the Airtable
   episode/guest record, not from memory or web search. Root-causes the EP35 company-name
   error. *Add a "verified" checkbox to the Airtable record that gates page generation.*
2. **One scripted "site-wiring" step.** `index.html` + `guests.html` + `episodes.html` +
   `sitemap.xml` are always edited together; today that's 4 manual edits prone to drift
   (counts, slugs). Collapse into a single generator/checklist so they can't diverge.
3. **Template-driven page generation.** Keep `episodes/<slug>.html` generation
   template-driven (or a small generator) so schema blocks, OG tags, and structure are
   identical every time — no per-episode hand-assembly.
4. **One PR per episode.** Once Riverside auto-transcript exists, build the page *with* the
   transcript in Stage 4 so there's a single PR, not a page PR + a transcript PR.
5. **Idempotent, validated deploys.** Always finish with the Stage 6 validation check
   (`commit_ref == main HEAD`, state `ready`) rather than assuming the deploy took.
6. **Everything lives in the repo.** This doc + the runbook + the generator/checklist are
   committed, so any cloud session executes the same steps with no tribal knowledge.

---

## 5. The per-episode runbook (tactical checklist)

The condensed, do-this-each-time version of Stages 4–6:

```
[ ] Pull verified metadata from Airtable (ep #, title, date, runtime, Buzzsprout ID)
[ ] Pull verified guest data (name, exact title/company, LinkedIn, bio, real outline)
[ ] Create episodes/<slug>.html from template
    [ ] title / meta description / canonical / OG (image = youtube maxresdefault)
    [ ] YouTube embed <ID>
    [ ] info card · show notes (real outline) · About + LinkedIn · Related Resources
    [ ] JSON-LD: PodcastEpisode + FAQPage + BreadcrumbList
[ ] Add assets/guests/<slug>.jpg (400x400 head-and-shoulders)
[ ] Wire site: index.html (cards + counts) · guests.html · episodes.html · sitemap.xml
[ ] Commit → push branch → draft PR
[ ] Verify Netlify deploy preview renders
[ ] Mark ready → squash-merge to main  (→ auto-deploys to staging)
[ ] (When available) add Full Episode Transcript section
[ ] Prod: Netlify → signalroom → Deploys → Trigger deploy → Deploy site
[ ] Validate prod: state=ready, commit_ref==main HEAD, build_id present, published today
[ ] Distribute: newsletter (Beehiiv) · social (LinkedIn/YouTube) · Slack notify
```

---

## 6. Running it in the cloud (multi-agent design)

The goal: a **smooth, consistent, repeatable** pipeline executed by **as many agents as
needed**, with humans only at the two gates (opportunity accept, prep review).

**Execution substrate:** Claude Code on the web (cloud sessions like this one) as the
compute; **Routines / scheduled triggers** as the clock and event source; GitHub + Airtable +
Drive + Netlify as the systems of record.

**Orchestration shape — an orchestrator + stage subagents:**

```
Orchestrator (per episode / per guest)
  ├─ Agent: Opportunity Assessment  → writes score to Airtable, notifies host (gate)
  ├─ Agent: Prep Brief              → drafts brief to Drive, notifies host (gate)
  ├─ Agent: Transcript ingest       → Riverside MCP → Drive + Airtable   (future)
  ├─ Agent: Page Builder            → episodes/<slug>.html + site wiring → draft PR
  ├─ Agent: Content Derivatives     → newsletter blurb + social posts (grounded in transcript + past eps)
  └─ Agent: Deploy & Validate       → prod trigger + deploy validation
```

**How each stage is triggered in the cloud:**
- **Scheduled** (Routine/cron): e.g., a daily sweep that checks Airtable for guests in
  `accepted` → kicks the Prep Brief agent; or checks for episodes whose go-live date is today
  → kicks Page Builder.
- **Event-driven:** PR webhooks already wake this session for CI/review; the same mechanism
  can carry the publish loop.
- **Human gates** stay human — four of them (§8): opportunity accept (G1), prep review (G2),
  newsletter/social approval (G3, auto-draft-and-hold), and prod go-live (G4, manual Trigger
  deploy). The agent prepares and notifies (Slack/email); a person approves.

---

## 7. Blockers to "flawless, repeatable" cloud execution

These must be resolved for the pipeline to run unattended:

1. **Connector stability.** Airtable, Routines, GitHub, and others flap in non-interactive
   cloud sessions ("requires approval" / "permission stream closed"). Scheduled agent runs
   need these authorized and stable (reconnect via claude.ai → connector settings).
2. **Three unauthorized connectors** (`142875f8…`, `6558f07b…`, `c7b655ce…`) need authorizing
   in claude.ai connector settings before their capability is even visible.
3. **Production deploy authorization.** This session's Netlify connector can *read* prod but
   is **not authorized to publish** it (Netlify returns `403`). The cloud pipeline needs a
   prod-authorized deploy path — a **build hook**, an account with publish rights, or the
   now-active Git auto-deploy on `main`.
4. **Routines connector must be readable/writable** to schedule the sweeps in §6 (couldn't be
   inventoried this session).
5. **Riverside FM MCP** is not yet connected — Stage 3 is manual until it is.

---

## 8. Decisions (confirmed)

The human-in-the-loop model is settled. **Four human gates**, everything else automated:

| # | Gate | Who approves | What the agent does |
|---|---|---|---|
| G1 | **Opportunity accept/decline** | Host | Scores the guest, writes rationale to Airtable, notifies — then waits |
| G2 | **Prep brief review** | Host | Drafts the prep brief to Drive, notifies — then waits |
| G3 | **Newsletter + social** | Host | **Auto-drafts and holds for approval** — never auto-publishes distribution content |
| G4 | **Production go-live** | Host | **Manual Netlify "Trigger deploy"** stays the gate; no auto-publish on merge to `main` |

Everything between the gates (enrichment, page build, staging merge, transcript, deploy
validation, draft generation) runs automatically.

### Airtable status vocabulary (confirmed from schema)

Pulled from the live base schema. The earlier assumed vocabulary was wrong — the real system
uses **two front-door tables** plus the episode table, each with its own field:

**`Guest Opportunities` (`tbl7BjmotGvcUtVa4`) → `Current Status`** — the inbound/opportunity
engine (the machine states — `needs_dedupe`, `needs_enrichment`, `draft_created` — indicate an
existing automation already populates this):
```
new_unreviewed → needs_dedupe → needs_enrichment → ready_for_review
   → strong_fit | conditional_fit | not_a_fit | hold_for_later   (← G1 assessment output)
   → needs_reply → draft_created → replied_waiting
   → booking_in_progress → booked → archived | error
```
Supporting selects on the same table:
- **`Classification`**: guest_pitch · podcast_invite · media_query · warm_intro · scheduling · follow_up · newsletter · sales_spam · irrelevant
- **`Priority`**: immediate · this_week · normal · low
- **`Recommended Next Action`**: reply_now · ask_for_more_info · add_to_review_queue · decline · archive · schedule · hold
- **`Draft Status`**: none → recommended → approved_to_create → created → stale · rejected  *(this is the G3 auto-draft-and-hold gate in field form)*

**`Guest Applications` (`tbloZMd3IzXNo20jY`) → `Status`** — the simpler guest-intake track:
```
New → Reviewing → Contacted → Scheduled → Recorded   (terminal: Declined · Spam)
```

**`Buzzsprout Episode Data` (`tblrji2ivwJQYE6Rg`)**:
- **`Buzzsprout Status`**: Draft → Scheduled → Published  (terminal: Deleted)
- **`Transcript Source`**: Buzzsprout · Manual Upload · **Third-Party Integration** *(← the future Riverside path)*

**Mapping to the pipeline gates:** G1 assessment writes `Guest Opportunities.Current Status`
(strong/conditional/not_a_fit) + `Recommended Next Action`; G3 draft-and-hold is
`Guest Opportunities.Draft Status` (`recommended` → host approves → `approved_to_create`).
The "staged" / "live" **site**-deploy states are *not* Airtable fields today — they live in
Netlify (staging = merged to `main`; live = prod deploy). If you want them tracked in Airtable,
add a `Site Status` select to `Buzzsprout Episode Data` (`staged` / `live`); flagged as a
recommendation, not built.
