# Guest materials OAuth

Private endpoint: `/mcp/private`. Public `/mcp` remains anonymous.

Microsoft Entra tenant: `24457a8d-f4e8-4771-b491-6a917d698b97`.
API registration: `025bc72e-52e8-4fc4-b29d-42c24ec2a92c`.
Approved connector: `e9c81893-6a51-4c77-87f3-4a5bec83527f`.
Delegated scope: `api://025bc72e-52e8-4fc4-b29d-42c24ec2a92c/materials.read`.

The API registration must set `api.requestedAccessTokenVersion` to `2`.
Configure the exact ChatGPT callback URI on the connector registration and provide
its credential directly to ChatGPT, never to source control or chat messages.
The issuer's discovery is Microsoft-hosted; this site is not an authorization server.

No user receives materials automatically. An operator must write a JSON record to
the `sr-review-access` Netlify Blob store at
`oauth/principals/{tenant-id}/{user-object-id}` containing
`{"enabled":true,"episodes":["approved-episode-slug"]}` after verifying the
guest's Entra object ID and intended episode access. Do not authorize by email claim.
No assignments were created during deployment.

Every call rechecks assignments and the existing `grants/{episode}` enabled flag.
Disable the principal assignment to revoke OAuth material access. The principal
record is independent of browser-session/email grants and must be managed explicitly.
The publisher directory is excluded. Only manifest-listed plain text, Markdown,
VTT, or SRT files up to 200 KB can be read. Media and HTML are not returned.

Deployment checks cover anonymous denial and metadata. End-to-end sign-in and
assigned-user access require completing ChatGPT callback/client configuration,
setting token version 2, and an explicitly approved test assignment.
