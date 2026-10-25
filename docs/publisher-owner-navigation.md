# Publisher owner navigation

The shared library remains `/review/publisher/`. The owner's sign-in entry is
`/review/publisher/owner/`; it is not linked from the guest-facing library.

The `sr-review-access` store holds `settings/publisher-owner` with an `enabled`
boolean and one normalized owner `email`. A code is emailed only to that account.
Owner codes expire after ten minutes, allow five attempts, and are consumed
atomically. Owner sessions live separately from guest sessions and expire after
30 days. Disabling the owner setting or changing its email revokes existing
owner sessions immediately. Signing out removes the current session.

The navigation is inserted server-side only for a valid owner session. It links
to the library, the main site, and an alphabetical menu built from the current
published package cards. Both anonymous and owner responses use no-store
headers. No public package HTML or media is rewritten to add the bar.

Owner forms use native navigation so successful sign-in or sign-out reloads the
correct server-rendered view. Existing guest form and download behavior stays
covered by the review tests.

Run `npm test` to verify owner-only rendering, guest access, session revocation,
code replay/attempt limits, and the existing review/download behavior.
