# Batch 7 integrated discoverability rollout

Status: approved and in implementation.

## Episodes

- EP09 `UpJJejIHN-4` - Keshavan Seshadri
- EP08 `ghk8jZeWw1k` - Carol Velandia
- EP07 `RWrbko3Uo60` - Susie Branagan
- EP06 `NGBbYZSdcLs` - Danette McGilvray
- EP05 `fwVp0NsSFSI` - Ritu Chakrawarty

## Website

Five dedicated `/watch/` pages are staged with self-canonicals, one long-form iframe, one `VideoObject`, exact upload timestamps and durations, reciprocal episode links, extensionless redirects, and standard/video sitemap entries.

## YouTube

Titles, tracked episode links, guest links, Susie Branagan's missing subject-playlist membership, and the existing primary channel comments were updated through the owner API. Cards, end screens, thumbnail uploads, and pin-state confirmation require YouTube Studio.

The live YouTube links intentionally point to the existing episode/transcript pages until the new watch pages are approved, merged, and deployed. They should be replaced with the approved watch-page UTMs after deployment.

## Caption drafts

The `captions/` directory contains owner exports of the five serving English ASR tracks. Only directly verified proper-name, organization-name, show-name, venue-name, and framework-name corrections were applied. These are review drafts, not upload-ready files. A human must listen through each episode and verify wording, punctuation, speaker changes, and timing before replacing the serving ASR tracks.
