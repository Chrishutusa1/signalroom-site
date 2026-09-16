# Episode page VideoObject — canonical template

**Every `episodes/<slug>.html` must carry this standalone `VideoObject` JSON-LD block** — the fourth block alongside `PodcastEpisode`, `FAQPage`, `BreadcrumbList`. It is **mandatory and CI-gated** (`.github/workflows/validate.yml` → "Every episode page has a VideoObject" fails the build if any episode page lacks one).

**Why the builder must emit it directly:** the VideoObject used to live on the `/watch/<slug>` twin page. Those were **retired** in the 2026-09 `/watch`→`/episodes` consolidation (301'd to the hub), so a newly built episode page has no `/watch` to inherit from — the add-podcast-episode builder must author the block itself.

## Placement rules
- **Standalone** top-level `<script type="application/ld+json">` block in `<head>`, next to the other three JSON-LD blocks.
- **Do NOT** nest it inside `PodcastEpisode.associatedMedia` — that field is the Buzzsprout **audio** `MediaObject` (`{"@type":"MediaObject","contentUrl":"https://www.buzzsprout.com/2550733/episodes/<id>"}`).
- `@id` = `…/episodes/<slug>#video`; `url` and `mainEntityOfPage` = the episode's extensionless canonical.
- **Never add `hasPart`.** Google treats `VideoObject.hasPart` as key-moment `Clip`s (required: `name`, `startOffset`, `url` pointing into this same video). Shorts are separate YouTube videos, so they fail that validation. They belong only in the visible reel. CI fails any episode page whose VideoObject has `hasPart`.

## Template (fill the placeholders)
```html
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "VideoObject",
  "@id": "https://signalroompodcast.com/episodes/<SLUG>#video",
  "name": "<video title>",
  "description": "<1-2 sentence video description>",
  "thumbnailUrl": ["https://i.ytimg.com/vi/<YT_VIDEO_ID>/maxresdefault.jpg"],
  "uploadDate": "<ISO-8601, e.g. 2026-07-07T18:15:16Z>",
  "duration": "<ISO-8601, e.g. PT30M15S>",
  "embedUrl": "https://www.youtube.com/embed/<YT_VIDEO_ID>",
  "contentUrl": "https://www.youtube.com/watch?v=<YT_VIDEO_ID>",
  "url": "https://signalroompodcast.com/episodes/<SLUG>",
  "mainEntityOfPage": "https://signalroompodcast.com/episodes/<SLUG>",
  "isFamilyFriendly": true,
  "publisher": {
    "@type": "Organization",
    "name": "The Signal Room",
    "url": "https://signalroompodcast.com/",
    "logo": {"@type": "ImageObject", "url": "https://signalroompodcast.com/assets/logos/Signal_Room_Cover_FINAL_v2.png"}
  }
}
</script>
```

## When the shorts-injection pass adds clips
Shorts go **only** into the visible reel (`.episode-shorts-card`). Do not write them into the VideoObject.

- **Never** put the episode's own full video (the VideoObject `embedUrl` ID) in the reel. On 2026-09-16, 8 reels were found listing their own 20 to 60 minute episode as a "short", and those cards were removed.
- If removing an item empties a reel, remove the whole `.episode-shorts-card`. A page with no shorts has no carousel, same as a brand-new page.
- Both rules are enforced by the `validate.yml` gate "VideoObject has no hasPart; reels never list the page's own episode".

Key-moment `Clip` markup would be valid only with real start and end offsets into the full episode video. Never estimate or invent offsets. Shorts→episode attribution is governed by `episode-assets/shorts-attribution-spec.md`.
