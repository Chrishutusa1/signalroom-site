# Batch 6 integrated discoverability rollout

Status: approved and staged for review.

## Episodes

- EP14 `mMtwcZBCzb8` — Parth Gargish
- EP13 `8Yyji02GH7c` — Aleida Lanza
- EP12 `qYeC8dMRmJ4` — Asha Mahesh
- EP11 `SY9xtWnOSOE` — Amit Shivpuja
- EP10 `FhmwMJsVPB8` — Anitha Mareedu

## Website

This batch adds five dedicated `/watch/` pages, reciprocal links from the existing episode pages, standard sitemap entries, and complete video sitemap entries. Each watch page has a self-canonical URL, one privacy-enhanced YouTube iframe, and one `VideoObject` with the verified upload timestamp and duration.

## YouTube

The approved titles and descriptions are live. Descriptions use temporary, tracked episode-page links until the watch pages are deployed. The five videos were already present in the main video playlist and their appropriate topical playlists, so no playlist writes were necessary.

YouTube rejected the first attempted top-level comment update with HTTP 403, so no comments were changed. Comment updates and pinning, plus cards, end screens, and thumbnail decisions, remain Studio-only follow-up items.

## Caption drafts

The `captions/` directory contains YouTube English automatic-caption exports for review. Only six directly verified guest-name errors were corrected: Parth Gargish, Aleida Lanza, Amit Shivpuja, and three Anitha Mareedu mentions. These drafts require a complete human listen-through before upload or publication.

## Post-deployment follow-up

After the watch pages are merged and deployed, replace the temporary YouTube description links with the corresponding `/watch/` URLs using the same UTM parameters, validate the five live URLs and both sitemaps, and submit or inspect them in Google Search Console.
