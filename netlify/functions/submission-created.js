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

// Best-effort new-application notification via Resend, direct (no relay).
// Never throws — a notification failure must not lose the application (already
// stored in Netlify Forms + Airtable).
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
    `<p><b>Airtable:</b> ${escapeHtml(airtableStatus)}${recordId ? ` (${escapeHtml(recordId)})` : ""}</p>`;

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
// Airtable write fails. The Zapier webhook is the primary alert, but two June
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
          `The Airtable write for a guest application FAILED (${airtableStatus}). ` +
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
  // A transient 429/5xx or network blip is retried before we declare failure —
  // an unretried transient error is the most likely cause of the 2026-06-29
  // silent lost-application (Boris Berenberg). A 4xx (bad token/schema) won't
  // heal on retry, so we stop immediately and let sendFailureAlert fire.
  const isRetryable = (status) => status === 429 || (status >= 500 && status <= 599);
  let airtableStatus = "ok";
  let recordId = null;
  const MAX_ATTEMPTS = 3;
  for (let attempt = 1; attempt <= MAX_ATTEMPTS; attempt++) {
    try {
      const resp = await fetch(url, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${AIRTABLE_PAT}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ records: [{ fields }], typecast: true }),
      });
      if (resp.ok) {
        const json = await resp.json();
        recordId = json.records?.[0]?.id || null;
        airtableStatus = "ok";
        break;
      }
      airtableStatus = `error ${resp.status}`;
      console.error(`Airtable write failed (attempt ${attempt}/${MAX_ATTEMPTS})`, resp.status, await resp.text());
      if (!isRetryable(resp.status)) break;
    } catch (err) {
      airtableStatus = "exception";
      console.error(`Airtable write threw (attempt ${attempt}/${MAX_ATTEMPTS})`, err);
    }
    if (attempt < MAX_ATTEMPTS) {
      await new Promise((r) => setTimeout(r, 400 * attempt)); // 400ms, 800ms backoff
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
