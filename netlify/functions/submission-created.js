/**
 * submission-created
 *
 * Netlify's reserved handler name — invoked automatically on every Netlify Forms
 * submission. Filters to the `guest-application` form and forwards it into
 * Airtable Content Intelligence Hub → `Guest Applications` table
 * (app3hF8k8ZGXvf9XF / tbloZMd3IzXNo20jY), then fires a best-effort
 * new-application notification + on-brand auto-reply.
 *
 * Required env vars (Netlify → Environment variables, scope: functions):
 *   AIRTABLE_PAT                - personal access token w/ data.records:write on the base
 *   AIRTABLE_BASE_ID            - app3hF8k8ZGXvf9XF
 *   AIRTABLE_GUEST_APPS_TABLE   - "Guest Applications" (table name or table ID)
 *
 * Optional env vars (scope: functions):
 *   LEAD_NOTIFY_WEBHOOK_URL - incoming webhook for new-application alerts. Posts
 *       flat, form-encoded fields (summary, name, email, title, linkedin, theme,
 *       topics, context, airtable_status). If unset, notification is skipped.
 *   RESEND_API_KEY  - Resend API key for the on-brand auto-reply to the applicant.
 *   AUTOREPLY_FROM  - verified sender, e.g. "The Signal Room <chris@hutchinsdatastrategy.com>".
 *       If either is unset, the auto-reply is skipped.
 */

// A hostile submission can push multi-KB strings into Airtable and the
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

// Best-effort new-application notification. Never throws — a notification failure
// must not lose the application (already stored in Netlify Forms + Airtable).
async function notifyApplication(fields, airtableStatus, recordId) {
  const webhook = process.env.LEAD_NOTIFY_WEBHOOK_URL;
  if (!webhook) return;

  const summary = [
    `New guest application (Signal Room) — ${fields.Name || "(no name)"}`,
    `Email: ${fields.Email || "—"}`,
    `Title & Org: ${fields["Title & Organization"] || "—"}`,
    `LinkedIn: ${fields.LinkedIn || "—"}`,
    `Theme: ${fields.Theme || "—"}`,
    fields.Topics ? `Topics: ${fields.Topics}` : null,
    fields.Context ? `Context: ${fields.Context}` : null,
    `Airtable: ${airtableStatus}${recordId ? ` (${recordId})` : ""}`,
  ]
    .filter(Boolean)
    .join("\n");

  const body = new URLSearchParams({
    summary,
    name: fields.Name || "",
    email: fields.Email || "",
    title: fields["Title & Organization"] || "",
    linkedin: fields.LinkedIn || "",
    theme: fields.Theme || "",
    topics: fields.Topics || "",
    context: fields.Context || "",
    airtable_status: airtableStatus,
  }).toString();

  try {
    await fetch(webhook, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body,
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

exports.handler = async (event) => {
  if (event.httpMethod !== "POST") {
    return { statusCode: 405, body: "Method Not Allowed" };
  }

  const { AIRTABLE_PAT, AIRTABLE_BASE_ID, AIRTABLE_GUEST_APPS_TABLE } = process.env;
  if (!AIRTABLE_PAT || !AIRTABLE_BASE_ID || !AIRTABLE_GUEST_APPS_TABLE) {
    return {
      statusCode: 500,
      body: "Server misconfigured: missing Airtable env vars.",
    };
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

  const url = `https://api.airtable.com/v0/${AIRTABLE_BASE_ID}/${encodeURIComponent(AIRTABLE_GUEST_APPS_TABLE)}`;

  // Write to Airtable, capturing status so we can always notify (and avoid
  // non-2xx returns that would trigger Netlify retries → duplicate alerts).
  let airtableStatus = "ok";
  let recordId = null;
  try {
    const resp = await fetch(url, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${AIRTABLE_PAT}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ records: [{ fields }], typecast: true }),
    });
    if (!resp.ok) {
      airtableStatus = `error ${resp.status}`;
      console.error("Airtable write failed", resp.status, await resp.text());
    } else {
      const json = await resp.json();
      recordId = json.records?.[0]?.id || null;
    }
  } catch (err) {
    airtableStatus = "exception";
    console.error("Airtable write threw", err);
  }

  await notifyApplication(fields, airtableStatus, recordId);
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
