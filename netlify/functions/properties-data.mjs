// Shared server-side storage for the Property Manager app (/app/properties/).
//
// Functions v2 handler served at /api/properties-data (see `config` below).
// Storage is Neon Postgres (project delicate-leaf-67982487): tables
// property_app, agent_app (FK property_app_id -> property_app, ON DELETE
// CASCADE), and app_kv holding the sync timestamp under key 'updatedAt'. The
// app syncs its whole state per request (single-user, last-write-wins).
//
// Migrated off Airtable 2026-11-15: the Property Manager Airtable base
// (appgNkAc7lFFUi086) was retired as the runtime store so the app no longer
// depends on the Airtable API (which was exhausting its monthly quota). The
// one-time data copy came from the 2026-11-03 Airtable backup. Agents and
// properties are keyed by their stable "App ID" (`app_id`), unchanged from the
// Airtable model, so existing app clients keep working.
//
// Env vars (set on both Netlify sites):
//   PROPERTIES_SYNC_KEY  shared secret; requests carry it in X-Sync-Key.
//                        Without it the endpoint is disabled (503), so a
//                        fresh fork can never expose an open endpoint.
//   DATABASE_URL         Neon pooled connection string (same database the
//                        guest-application function uses). Replaced the
//                        AIRTABLE_TOKEN / PROPERTIES_AIRTABLE_BASE_ID vars.

import { timingSafeEqual, createHash } from "node:crypto";
import { neon } from "@neondatabase/serverless";

export const config = { path: "/api/properties-data" };

const MAX_BYTES = 512 * 1024;
const STATUSES = new Set(["active", "paused", "error", "idle"]);

function json(body, status) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", "Cache-Control": "no-store" },
  });
}

// Constant-time compare of two strings of arbitrary length (hash first so
// timingSafeEqual's equal-length requirement is always met).
function safeEqual(a, b) {
  const ha = createHash("sha256").update(String(a)).digest();
  const hb = createHash("sha256").update(String(b)).digest();
  return timingSafeEqual(ha, hb);
}

const db = () => neon(process.env.DATABASE_URL);

async function handleGet() {
  const sql = db();
  const [props, agents, kv] = await Promise.all([
    sql`SELECT app_id, name, url, notes, ord FROM property_app ORDER BY ord, name`,
    sql`SELECT app_id, property_app_id, name, role, status, last_run_at, last_run_outcome, last_run_note, ord
          FROM agent_app ORDER BY ord, name`,
    sql`SELECT value FROM app_kv WHERE key = 'updatedAt'`,
  ]);

  const byId = new Map();
  const properties = props.map((r) => {
    const p = {
      id: r.app_id,
      name: String(r.name || "").trim() || "(unnamed)",
      url: r.url || "",
      notes: r.notes || "",
      agents: [],
    };
    byId.set(r.app_id, p);
    return p;
  });

  for (const a of agents) {
    const parent = byId.get(a.property_app_id);
    if (!parent) continue; // agent with no property link is invisible to the app
    parent.agents.push({
      id: a.app_id,
      name: String(a.name || "").trim() || "(unnamed)",
      role: a.role || "",
      status: STATUSES.has(a.status) ? a.status : "idle",
      lastRun: a.last_run_at
        ? {
            at: new Date(a.last_run_at).toISOString(),
            outcome: a.last_run_outcome === "failure" ? "failure" : "success",
            note: a.last_run_note || "",
          }
        : null,
    });
  }

  const updatedAt = kv.length ? kv[0].value || null : null;
  return json({ version: 1, updatedAt, properties }, 200);
}

async function handlePut(doc, clientBase) {
  const sql = db();

  // Optimistic concurrency: if the store has ever been written, the client
  // must present the updatedAt it last pulled. A mismatch means another
  // device wrote since — refuse the overwrite instead of silently deleting
  // whatever the stale client doesn't know about.
  const cur = await sql`SELECT value FROM app_kv WHERE key = 'updatedAt'`;
  const serverBase = cur.length ? cur[0].value || "" : "";
  if (serverBase && clientBase !== serverBase) {
    return json(
      { error: "conflict: the shared data changed since this device last pulled", updatedAt: serverBase },
      409
    );
  }

  const updatedAt = typeof doc.updatedAt === "string" ? doc.updatedAt : new Date().toISOString();
  const keepProps = doc.properties.map((p) => p.id);
  const keepAgents = doc.properties.flatMap((p) => p.agents.map((a) => a.id));

  const queries = [];
  doc.properties.forEach((p, i) => {
    queries.push(sql`
      INSERT INTO property_app (app_id, name, url, notes, ord)
      VALUES (${p.id}, ${p.name}, ${p.url || ""}, ${p.notes || ""}, ${i})
      ON CONFLICT (app_id) DO UPDATE
        SET name = excluded.name, url = excluded.url, notes = excluded.notes, ord = excluded.ord`);
  });
  doc.properties.forEach((p) => {
    p.agents.forEach((a, i) => {
      const status = STATUSES.has(a.status) ? a.status : "idle";
      queries.push(sql`
        INSERT INTO agent_app (app_id, property_app_id, name, role, status, last_run_at, last_run_outcome, last_run_note, ord)
        VALUES (${a.id}, ${p.id}, ${a.name}, ${a.role || ""}, ${status},
                ${a.lastRun ? a.lastRun.at : null},
                ${a.lastRun ? (a.lastRun.outcome === "failure" ? "failure" : "success") : null},
                ${a.lastRun ? a.lastRun.note || "" : null}, ${i})
        ON CONFLICT (app_id) DO UPDATE
          SET property_app_id = excluded.property_app_id, name = excluded.name, role = excluded.role,
              status = excluded.status, last_run_at = excluded.last_run_at,
              last_run_outcome = excluded.last_run_outcome, last_run_note = excluded.last_run_note,
              ord = excluded.ord`);
    });
  });
  // Delete agents first so no row ever points at a deleted property.
  // (= ANY('{}') is false for every row, so an empty keep-list clears the table.)
  queries.push(sql`DELETE FROM agent_app WHERE NOT (app_id = ANY(${keepAgents}))`);
  queries.push(sql`DELETE FROM property_app WHERE NOT (app_id = ANY(${keepProps}))`);
  queries.push(sql`
    INSERT INTO app_kv (key, value) VALUES ('updatedAt', ${updatedAt})
    ON CONFLICT (key) DO UPDATE SET value = excluded.value`);

  await sql.transaction(queries);
  return json({ ok: true, updatedAt }, 200);
}

export default async (req) => {
  const expected = process.env.PROPERTIES_SYNC_KEY;
  if (!expected || !process.env.DATABASE_URL) {
    return json({ error: "sync is not configured on this site" }, 503);
  }
  const provided = req.headers.get("x-sync-key") || "";
  if (!provided || !safeEqual(provided, expected)) {
    return json({ error: "invalid sync key" }, 401);
  }

  try {
    if (req.method === "GET") return await handleGet();

    if (req.method === "PUT") {
      const text = await req.text();
      if (new TextEncoder().encode(text).length > MAX_BYTES) {
        return json({ error: "payload too large" }, 413);
      }
      let doc;
      try {
        doc = JSON.parse(text);
      } catch {
        return json({ error: "body is not valid JSON" }, 400);
      }
      const shapeOk =
        doc && typeof doc === "object" && Array.isArray(doc.properties) &&
        doc.properties.every(
          (p) =>
            p && typeof p.id === "string" && typeof p.name === "string" && Array.isArray(p.agents) &&
            p.agents.every((a) => a && typeof a.id === "string" && typeof a.name === "string")
        );
      if (!shapeOk) return json({ error: "not a property-manager document" }, 422);
      return await handlePut(doc, req.headers.get("x-base-updated-at") || "");
    }

    return json({ error: "method not allowed" }, 405);
  } catch (err) {
    console.error("properties-data:", err);
    return json({ error: "storage backend error" }, 502);
  }
};
