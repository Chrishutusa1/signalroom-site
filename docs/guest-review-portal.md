# Guest review rooms

Private review packages are served only through `/review/<episode>/`. They are absent from the public site's menus, sitemap, repository, and static deploy. The edge handler authenticates both the gallery and every media/download request. Content lives in the private `sr-review-content` Netlify Blobs store; approved email lists and expiring sessions live in the strongly consistent `sr-review-access` store.

Guests request an eight-digit, ten-minute code through the page. Resend sends to approved addresses only, using existing `RESEND_API_KEY` and `AUTOREPLY_FROM` runtime variables. Codes are hashed with a random salt, limited to five guesses, consumed with an atomic conditional write, and never logged. Email/IP request limits and same-origin POST checks apply. Session cookies are HttpOnly, Secure, SameSite=Strict, scoped to the episode and valid for eight hours. Every request rereads the episode's approved addresses, so removing an address revokes active access immediately.

The local `tools/review-admin.mjs` operator tool uses the already authenticated Netlify CLI account without writing or printing credentials. `upload <episode> <absolute-package-path>` uploads the completed episode assets and verifies SHA-256 metadata before publishing the private manifest. `grant <episode> <email> [email...]` replaces the approved address list; include the owner as well as the guest. Grants never send an invitation. The owner shares the review URL separately.

The public Google Drive copy must have Anyone-with-link access removed once migration is verified. Restrict that package folder only; never alter unrelated Drive folders. Review links should point to the website thereafter.

`npm test` verifies unauthorized file denial, invite checks, one-time code consumption, concurrent verification, attempt limits, expiry, same-origin protection, logout, immediate grant revocation and episode isolation. Before production promotion also verify a deployed preview, including seeking via authenticated HTTP Range requests, unauthenticated direct-file denial, and signed-out rendering. Private media requests return no-store and noindex headers.

Expired challenge/session records contain hashes and email identifiers in private storage and do not grant access. Routine deletion of expired records can be added as operational maintenance. No guest analytics or public listing is enabled.
