# GitHub Actions workflows

| Workflow | Trigger | Purpose |
|---|---|---|
| `validate.yml` | push / PR | **CI publish gates** — meta≤155, title≤57, shorts alt, single `style.css?v=`, sitemap freshness, `_redirects` shape. Blocks merges that carry the recurring defect classes. |
| `episode-ops.yml` | schedule + manual | **Scheduled episode-ops lane** — the cloud port of the local `episode-prep-check` / `episode-publish-verify` tasks. Read-only v1: checks upcoming-episode metadata in Airtable and verifies episodes are live/consistent on staging + prod. |

## `episode-ops.yml` — required secret

Add under **Settings → Secrets and variables → Actions**:

- **`AIRTABLE_TOKEN`** — Airtable personal access token with `data.records:read` on base
  `app3hF8k8ZGXvf9XF` (Content Intelligence Hub). Without it the metadata step degrades to a
  warning (the run stays green), so the workflow is safe to merge before the secret exists.

## What `episode-ops.yml` intentionally does **not** do

- **No production deploy.** Production **auto-publishes** from `main` via Netlify continuous
  deployment on merge — deploying is Netlify's job, not the workflow's. This lane only
  **verifies** the deploy landed. The safety gate is the PR + `validate.yml` CI + staging
  preview *before* merge (`docs/CONTENT-OPS-PIPELINE.md` §8).
- **No page build.** Building `episodes/<slug>.html` + wiring stays the agent + PR flow.
- **No Airtable writes** in v1 (heartbeat-row logging is a documented TODO).

## Why this exists

Almost all Signal Room automation runs **locally** (a "computer-on" `scheduled-tasks.json`).
Only `podcast-stats-cloud` runs cloud-native (GitHub Actions, private repo
`signalroom-stats-pipeline`). `episode-ops.yml` starts porting the episode lane onto that same
cloud model so the pipeline runs even when no local machine is on. See
`docs/AUTOMATION-INVENTORY.md` for the full inventory and migration plan.

## Cadence (CT → UTC, CT = UTC-5)

| Task | Local | UTC cron |
|---|---|---|
| prep-check | Tue 16:00 CT | `0 21 * * 2` |
| verify (post auto-deploy) | Wed 08:00 CT | `0 13 * * 3` |

> Note: GitHub Actions `schedule` runs on the **default branch** only, and cron times drift
> under heavy load. Adjust the offset if daylight time changes CT to UTC-6.
