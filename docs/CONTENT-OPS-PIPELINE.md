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
| **Airtable — "Content Intelligence Hub"** | Pipeline database & single source of truth for guests + episode metadata | base `app3hF8k8ZGXvf9XF` · Buzzsprout Episode Data `tblrji2ivwJQYE6Rg` · Guest Applications (prep) `tbloZMd3IzXNo20jY` · Credential Inventory `tblQtQjrJkbk2GuEk` · Master credentials `tbldkMjFsrBSHO76q` |
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
- **GitHub Actions / workflows:** none in the repo.
- **Deploy scripts in repo:** none (`netlify.toml` config only; `publish = "."`).
- **Routines / scheduled triggers:** could not be read (connector instability at scan time — see §7).
- **Net effect:** there is currently **no scheduled or event-driven automation**. Every stage
  below is driven manually inside a single working session. Making this "run in the cloud"
  means converting the stages into scheduled/triggered agent runs (§6).

---

## 3. The pipeline (stage by stage)

Each stage names its **trigger**, the **agent work**, the **human gate**, and the
**system-of-record update** so any cloud session can execute it identically.

### Stage 1 — Guest Opportunity Assessment
- **Trigger:** new inbound guest (Airtable *Guest Applications* row / intake form).
- **Agent work:** enrich the applicant (role, company, LinkedIn, relevance to healthcare-AI
  audience); score against ICP using prior episodes as the yardstick; write a recommendation.
- **System update:** write score + rationale + status (`assess`) back to the applicant's
  Airtable row.
- **Human gate:** host accepts / declines.
- **Output:** qualified guest with a decision recorded in Airtable.

### Stage 2 — Guest Prep Review
- **Trigger:** guest accepted + recording scheduled.
- **Agent work:** gather bio + headshot + company from Drive `GuestData/<Guest>` and Airtable;
  fill gaps from the web; draft a **prep brief** (angle, 8–10 question outline, risk/verify
  notes — e.g. exact company/title); ensure the Drive guest folder exists and is populated.
- **System update:** prep brief saved to the guest's Drive folder + linked in Airtable;
  status → `prepped`.
- **Human gate:** host reviews/edits the prep brief before recording.

### Stage 3 — Record  *(future: Riverside FM MCP)*
- **Trigger:** recording completed in Riverside.
- **Agent work:** pull the recording + **auto-transcript** via the Riverside MCP; store the
  transcript in `GuestData/<Guest>` and attach to the Airtable episode record.
- **System update:** episode row gets transcript + raw asset links; status → `recorded`.
- *Until Riverside MCP exists:* transcript is added manually when supplied (Stage 5).

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
- **System update:** merge to `main` **auto-deploys to staging**; episode status → `staged`.

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
- **System update:** episode status → `live`.

### Stage 7 — Distribution & visibility
- **Trigger:** episode `live`.
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
- **Human gates** stay human: the agent prepares and notifies (Slack/email), a person approves.

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

## 8. Open questions for review

- Which stages should be **fully automated** vs kept **human-gated** beyond the two named?
- Newsletter/social: auto-draft-and-hold for approval, or auto-publish?
- Prod go-live: keep the manual **Trigger deploy** gate, or enable auto-publish on merge to
  `main` (with "Stop auto publishing" off)?
- Confirm the Airtable status vocabulary (`assess → accepted → prepped → recorded → staged →
  live`) matches the real field values in *Guest Applications* / *Buzzsprout Episode Data*.
