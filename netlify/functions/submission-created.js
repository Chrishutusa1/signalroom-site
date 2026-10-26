/**
 * submission-created
 *
 * Netlify's reserved handler name — invoked automatically on every Netlify Forms
 * submission. Filters to the `guest-application` form and forwards it into
 * the Neon `guest_application` table (hdsc-intelligence schema; replaced the
 * Airtable Guest Applications table 2026-10-26), then fires a best-effort
 * new-application notification + on-brand auto-reply.
 *
 * Required env vars (Netlify → Environment variables, scope: functions):
 *   DATABASE_URL  - Neon pooled connection string (same database as the
 *                   hdsc-intelligence repo). Replaced the AIRTABLE_* vars 2026-10-26.
 *
 * Optional env vars (scope: functions):
 *   LEAD_NOTIFY_TO  - comma-separated recipient(s) for new-application alerts,
 *       sent via Resend. Defaults to chris@hutchinsdatastrategy.com if unset.
 *   RESEND_API_KEY  - Resend API key, used for both the new-application alert and
 *       the on-brand auto-reply to the applicant.
 *   AUTOREPLY_FROM  - verified sender, e.g. "The Signal Room <chris@hutchinsdatastrategy.com>".
 *       If either RESEND_API_KEY or AUTOREPLY_FROM is unset, both the alert and
 *       the auto-reply are skipped.
 *
 * 2026-09-04: replaced LEAD_NOTIFY_WEBHOOK_URL (a Zapier catch hook) with a
 * direct Resend send after the Zapier account was deinstalled — no third-party
 * relay in the notification path anymore.
 */

// A hostile submission can push multi-KB strings into the database and the
// notification webhook (GAPS #10) — clip every user-supplied field.
const clip = (s, n = 1000) => String(s ?? "").slice(0, n);

// Trivial shape check only — full validation is not the goal; this just keeps
// the auto-reply from mailing garbage addresses.
const looksLikeEmail = (s) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(s);

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

// Best-effort new-application notification via Resend, direct (no relay).
// Never throws — a notification failure must not lose the application (already
// stored in Netlify Forms + the database).
async function notifyApplication(fields, airtableStatus, recordId) {
  const apiKey = process.env.RESEND_API_KEY;
  const from = process.env.AUTOREPLY_FROM;
  if (!apiKey || !from) return;

  const to = (process.env.LEAD_NOTIFY_TO || "chris@hutchinsdatastrategy.com")
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);

  const html =
    `<h2>New guest application (Signal Room) — ${escapeHtml(fields.Name) || "(no name)"}</h2>` +
    `<p><b>Email:</b> ${escapeHtml(fields.Email) || "-"}<br>` +
    `<b>Title &amp; Org:</b> ${escapeHtml(fields["Title & Organization"]) || "-"}<br>` +
    `<b>LinkedIn:</b> ${escapeHtml(fields.LinkedIn) || "-"}<br>` +
    `<b>Theme:</b> ${escapeHtml(fields.Theme) || "-"}</p>` +
    (fields.Topics ? `<p><b>Topics:</b> ${escapeHtml(fields.Topics)}</p>` : "") +
    (fields.Context ? `<p><b>Context:</b> ${escapeHtml(fields.Context)}</p>` : "") +
    `<p><b>Database:</b> ${escapeHtml(airtableStatus)}${recordId ? ` (${escapeHtml(recordId)})` : ""}</p>`;

  try {
    await fetch("https://api.resend.com/emails", {
      method: "POST",
      headers: { Authorization: `Bearer ${apiKey}`, "Content-Type": "application/json" },
      body: JSON.stringify({
        from,
        to,
        reply_to: fields.Email || undefined,
        subject: `New guest application (Signal Room) — ${fields.Name || "(no name)"}`,
        html,
      }),
    });
  } catch (err) {
    console.error("application notification failed (non-fatal)", err);
  }
}

// Best-effort on-brand auto-reply to the applicant via Resend. Skipped unless
// RESEND_API_KEY + AUTOREPLY_FROM are set and the applicant provided an email.
async function sendAutoReply(fields) {
  const apiKey = process.env.RESEND_API_KEY;
  const from = process.env.AUTOREPLY_FROM;
  if (!apiKey || !from || !fields.Email) return;

  const firstName = (fields.Name || "").trim().split(/\s+/)[0] || "there";
  const subject = "Thanks for applying to The Signal Room";
  const html =
    `<p>Hi ${escapeHtml(firstName)},</p>` +
    `<p>Thank you for your interest in being a guest on <strong>The Signal Room</strong>. We will review your information and follow up with you within a few days to coordinate a brief intro call to discuss topics and possible scheduling.</p>` +
    `<p>While you wait, a couple of episodes that show how we structure these conversations:</p>` +
    `<ul>` +
    `<li><a href="https://signalroompodcast.com/episodes">Recent episodes</a> — see who's been on and what we've covered</li>` +
    `<li><a href="https://signalroompodcast.com/about">About the show</a> — the audience and the editorial point of view</li>` +
    `</ul>` +
    `<p>— Christopher Hutchins<br>Host, The Signal Room</p>`;
  const text =
    `Hi ${firstName},\n\n` +
    `Thank you for your interest in being a guest on The Signal Room. We will review your information and follow up with you within a few days to coordinate a brief intro call to discuss topics and possible scheduling.\n\n` +
    `While you wait, two links worth your time:\n` +
    `- Recent episodes: https://signalroompodcast.com/episodes\n` +
    `- About the show: https://signalroompodcast.com/about\n\n` +
    `— Christopher Hutchins\nHost, The Signal Room`;

  try {
    await fetch("https://api.resend.com/emails", {
      method: "POST",
      headers: { Authorization: `Bearer ${apiKey}`, "Content-Type": "application/json" },
      body: JSON.stringify({
        from,
        to: [fields.Email],
        reply_to: "chris@hutchinsdatastrategy.com",
        subject,
        html,
        text,
      }),
    });
  } catch (err) {
    console.error("auto-reply failed (non-fatal)", err);
  }
}

// Second alert channel (2026-07-14): email Chris directly via Resend when the
// database write fails. The Zapier webhook is the primary alert, but two June
// submissions proved a run can lose the lead with no webhook delivery — this
// path only shares fate with the auto-reply (Resend), not with Zapier.
async function sendFailureAlert(fields, airtableStatus) {
  const apiKey = process.env.RESEND_API_KEY;
  const from = process.env.AUTOREPLY_FROM;
  if (!apiKey || !from) return;
  try {
    await fetch("https://api.resend.com/emails", {
      method: "POST",
      headers: { Authorization: `Bearer ${apiKey}`, "Content-Type": "application/json" },
      body: JSON.stringify({
        from,
        to: ["chris@hutchinsdatastrategy.com"],
        subject: `LEAD WRITE FAILED (Signal Room guest form): ${fields.Name || "(no name)"}`,
        text:
          `The database write for a guest application FAILED (${airtableStatus}). ` +
          `The submission is safe in Netlify Forms; re-create the record or wait for the weekly reconciliation.\n\n` +
          `Name: ${fields.Name || "—"}\nEmail: ${fields.Email || "—"}\n` +
          `Title & Org: ${fields["Title & Organization"] || "—"}\n` +
          `Submitted At: ${fields["Submitted At"] || "—"}`,
      }),
    });
  } catch (err) {
    console.error("failure alert email failed (non-fatal)", err);
  }
}

exports.handler = async (event) => {
  if (event.httpMethod !== "POST") {
    return { statusCode: 405, body: "Method Not Allowed" };
  }


  let payload;
  try {
    payload = JSON.parse(event.body || "{}");
  } catch {
    return { statusCode: 400, body: "Invalid JSON" };
  }

  const submission = payload.payload || payload;
  const data = submission.data || {};

  const formName = submission.form_name || data["form-name"];
  if (formName === "sponsor-inquiry") {
    // The accepted submission remains in Netlify Forms; do not put sponsors in Guest Applications.
    if (data["bot-field"] || !looksLikeEmail(data.email)) return { statusCode: 200, body: "Ignored invalid inquiry." };
    const apiKey = process.env.RESEND_API_KEY;
    const from = process.env.AUTOREPLY_FROM;
    if (!apiKey || !from) return { statusCode: 500, body: "Sponsor inquiry saved in Netlify; notification configuration missing." };
    const to = (process.env.LEAD_NOTIFY_TO || "chris@hutchinsdatastrategy.com").split(",").map(s => s.trim()).filter(Boolean);
    const response = await fetch("https://api.resend.com/emails", {
      method: "POST",
      headers: { Authorization: `Bearer ${apiKey}`, "Content-Type": "application/json", "Idempotency-Key": `sponsor-${submission.id || event.headers?.["x-nf-event-id"] || require("node:crypto").createHash("sha256").update(event.body).digest("hex")}` },
      body: JSON.stringify({from, to, reply_to: clip(data.email, 254), subject: "New Signal Room sponsorship inquiry", text: `Name: ${clip(data.name,160)}\nOrganization: ${clip(data.organization,200)}\nEmail: ${clip(data.email,254)}\n\n${clip(data.message,4000)}\n\nSaved in Netlify Forms: sponsor-inquiry.`})
    });
    return response.ok ? {statusCode:200,body:"Sponsor inquiry notification sent."} : {statusCode:502,body:"Sponsor inquiry saved; notification failed."};
  }
  if (formName !== "guest-application") {
    return { statusCode: 200, body: "Ignored non-guest-application form." };
  }

  const fields = {
    Name: clip(data.name, 200),
    Email: clip(data.email, 320),
    "Title & Organization": clip(data.title, 300),
    LinkedIn: clip(data.linkedin, 500),
    Theme: clip(data.theme, 300),
    Topics: clip(data.topics),
    Context: clip(data.context, 2000),
    Source: "signalroompodcast.com guest-application",
    "Submitted At": submission.created_at || new Date().toISOString(),
    "Submission ID": clip(submission.id, 100),
    "User Agent": clip(submission.user_agent, 500),
    Referrer: clip(submission.referrer, 500),
    Status: "New",
  };

  // Netlify normally filters honeypot hits before invoking this function;
  // belt-and-suspenders in case a bot POSTs the form action directly.
  const honeypotTripped = Boolean(data["bot-field"]);

  // Write to the Neon guest_application table (hdsc-intelligence schema).
  // Airtable was retired as the store on 2026-10-26 after the base went
  // read-only. Status is captured rather than thrown so we always notify and
  // always return 200 (non-2xx triggers Netlify retries -> duplicate alerts).
  // A transient network error is retried; a repeated Netlify submission ID is
  // ignored by the unique key, so a retry can never duplicate the application.
  let airtableStatus = "ok"; // name kept: the alert/notify helpers and response use it
  let recordId = null;
  const dbUrl = process.env.DATABASE_URL;
  if (!dbUrl) {
    airtableStatus = "misconfigured";
  } else {
    const { neon } = require("@neondatabase/serverless");
    const sql = neon(dbUrl);
    const v = (k) => (fields[k] ? fields[k] : null);
    const MAX_ATTEMPTS = 3;
    for (let attempt = 1; attempt <= MAX_ATTEMPTS; attempt++) {
      try {
        const rows = await sql`
          insert into guest_application (
            submission_id, submitted_at, name, email, title_org, linkedin,
            theme, topics, context, source, referrer, user_agent, status
          ) values (
            ${v("Submission ID")}, ${fields["Submitted At"]}, ${v("Name")}, ${v("Email")},
            ${v("Title & Organization")}, ${v("LinkedIn")}, ${v("Theme")}, ${v("Topics")},
            ${v("Context")}, ${v("Source")}, ${v("Referrer")}, ${v("User Agent")}, 'New'
          )
          on conflict (submission_id) do nothing
          returning id`;
        recordId = rows[0] ? String(rows[0].id) : null;
        airtableStatus = "ok";
        break;
      } catch (err) {
        airtableStatus = "exception";
        console.error(`Guest application write to Neon failed (attempt ${attempt}/${MAX_ATTEMPTS})`, err);
      }
      if (attempt < MAX_ATTEMPTS) {
        await new Promise((r) => setTimeout(r, 400 * attempt)); // 400ms, 800ms backoff
      }
    }
  }

  await notifyApplication(fields, airtableStatus, recordId);
  if (airtableStatus !== "ok") {
    await sendFailureAlert(fields, airtableStatus);
  }
  // Never auto-reply to a honeypot hit or a malformed address — the reply is an
  // open sender of Signal-Room-branded mail to whatever address was typed (GAPS #10).
  if (!honeypotTripped && looksLikeEmail(fields.Email)) {
    await sendAutoReply(fields);
  }

  return {
    statusCode: 200,
    body: JSON.stringify({ ok: airtableStatus === "ok", airtableStatus, recordId }),
  };
};
