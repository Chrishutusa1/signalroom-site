# Spec — Fix shorts→episode attribution in the shorts-generation routine

**Status:** proposed (2026-09-15). **Owner:** the claude.ai cloud "shorts-generation / add-podcast-episode" routine (NOT in this repo). **Why:** an audit on 2026-09-15 found ~84% of verifiable episode-clips were parented to the *wrong* episode, which the injector then rendered onto the wrong episode page. This spec makes the assignment deterministic.

## 1. The bug (root cause)

- `capture.py` (repo `Chrishutusa1/signalroom-stats-pipeline`, `podcast_stats_capture/capture.py`) upserts every Short's **raw** metadata into Airtable Shorts table `tblan7fxvxW0kpti2` (base `app3hF8k8ZGXvf9XF`), keyed on **YouTube Video ID**. It correctly leaves **`Parent Episode` blank**.
- A **separate** automated step sets `Parent Episode` **and** writes the clip's YouTube description. It does this by **topic/semantic guessing**, which:
  - assigns a thematically-similar but wrong episode (a Carly Caminiti "AI trust" clip → Larry Kuhn's leadership episode; a Guman Chauhan "AI liability" clip → Andre Samokish's governance episode), and
  - **hallucinates the guest name** in the description ("Dr. Anthony Caminiti" for Carly Caminiti; "Dr. Aloknath De Chauhan" for Guman Chauhan).
- The cloud **injector is correct** — it renders `Parent Episode` faithfully. Do not change the injector. Fix the assignment.

## 2. The authoritative signal

Every episode clip's YouTube description already contains the line:

```
Watch the full episode [with <Guest>]: https://youtu.be/<FULL_EPISODE_VIDEO_ID>
```

`<FULL_EPISODE_VIDEO_ID>` is the **actual source video** the clip was cut from. Map it to the episode:

- Podcast Episodes table `tblzKDGrxDnhFqQUU`, field **`YouTube Video ID`** (`fldtE2Tn5pDucjfpx`) holds each episode's full-video id. `youtu.be/<id>` → the episode record whose `YouTube Video ID` == `<id>`.

Set `Parent Episode` (linked-record field on the Shorts table → Podcast Episodes) to **that** record. Never infer it from topic, title, or publish date.

## 3. Required guardrails

1. **Corroboration gate (mandatory).** Only auto-set `Parent Episode` when the source-link episode's **guest surname** also appears in the clip description. Even source links are sometimes hallucinated (observed: clip `3CEsRmg-3Xw`, a radiology clip, links Gary Cao's CFO episode). If the surname does not corroborate → leave `Parent Episode` blank and set `Sync Status = "Needs review"` (do not guess).
2. **No fabricated names.** The description's `full episode with <Guest>` MUST be the real guest from the Podcast Episodes `Guest` field of the resolved episode — never an invented name. If the routine can't resolve a real guest, omit the name rather than invent one.
3. **No topic/date fallback.** If there is no source link and no corroborating name, do **not** assign a parent by theme or nearest-publish-date. Leave blank + flag.
4. **Idempotent.** Re-running must not churn already-correct rows.

## 4. Assignment algorithm (pseudocode)

```
episodes = PodcastEpisodes.rows()                      # tblzKDGrxDnhFqQUU
by_ytid  = { e["YouTube Video ID"]: e for e in episodes if e["YouTube Video ID"] }

for short in Shorts.rows():                            # tblan7fxvxW0kpti2
    desc = youtube.description(short["YouTube Video ID"])
    src  = first_id_matching(by_ytid, re.findall(r'youtu\.be/([\w-]{11})|watch\?v=([\w-]{11})', desc))
    if not src:                                        # no authoritative source link
        short["Sync Status"] = "Needs review"; continue
    ep       = by_ytid[src]
    surname  = ep["Guest"].split()[-1].lower()
    if surname not in desc.lower():                    # corroboration gate
        short["Sync Status"] = "Needs review"; continue
    set_if_changed(short, "Parent Episode", [ep.id])   # authoritative + corroborated
```

## 5. Description generation (same routine)

When the routine writes/updates a clip's description, the `full episode with <Guest>` name and the `youtu.be/<id>` link MUST both come from the **resolved episode record** (`Guest` + `YouTube Video ID`), so the two never disagree. This closes the loop: the description becomes a trustworthy source for the next run.

## 6. QA gate (add to the routine's finish step)

After assignment, run a check equivalent to the audit and fail loudly if any regression:
- For every Short with a `Parent Episode` AND a source link in its description: assert `Parent Episode.YouTube Video ID == youtu.be id`. Any mismatch = block + report.
- Report the count of `Sync Status = "Needs review"` (clips with no authoritative signal) for human triage.

## 7. One-time retro-fix (already partially done 2026-09-15)

- 23 existing `Parent Episode` values were corrected in Airtable from source links (1 low-confidence left). Re-running the algorithm above over the whole Shorts table will reconcile the rest.
- 28 embedded clips on the live site have **no source link** in their description and are content-unverifiable — they need a human to watch them (or the routine to regenerate their descriptions with a correct source link so the algorithm can then resolve them).

## 8. Page markup rules for injected shorts (added 2026-09-16)

These apply when the routine writes shorts onto an `episodes/<slug>.html` page:

- **Never write shorts into the `VideoObject` as `hasPart`.** Google reads `VideoObject.hasPart` as key-moment `Clip`s, which require `startOffset` and a `url` into the same video. Shorts are separate YouTube videos, so they fail that validation. Ahrefs flagged all 17 pages that had them on 2026-09-16, and `hasPart` was removed in PR #75. Shorts go only into the visible reel (`.episode-shorts-card`).
- **Never add the episode's own full video to its reel.** Skip any clip whose YouTube ID equals the page VideoObject `embedUrl` ID. 8 reels had done this.
- If a reel would end up empty, omit the whole `.episode-shorts-card`.
- `validate.yml` enforces both rules ("VideoObject has no hasPart; reels never list the page's own episode"), so a routine run that breaks them fails CI.

## Reference implementation

The audit + fix scripts that validate this spec live in this session's scratchpad: `injection_audit.py` (measures the mislabel rate), `resolve_all_embedded.py` / `reel_truth_audit.py` (source-link resolver), `airtable_parent_fix.py` (the corroboration-gated Airtable corrector).
