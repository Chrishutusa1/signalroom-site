// Shared server-side storage for the Property Manager app (/app/properties/).
//
// Functions v2 handler served at /api/properties-data (see `config` below).
// Storage is the "Property Manager" Airtable base: a Properties table, an
// Agents table (linked to Properties), and a Meta table holding the sync
// timestamp. The app syncs its whole state per request (single-user,
// last-write-wins); rows edited directly in Airtable show up in the app on
// its next pull. Zero npm dependencies — plain fetch against the Airtable
// REST API, keeping the repo package.json-free.
//
// Env vars (set on both Netlify sites):
//   PROPERTIES_SYNC_KEY  shared secret; requests carry it in X-Sync-Key.
//                        Without it the endpoint is disabled (503), so a
//                        fresh fork can never expose an open endpoint.
//   AIRTABLE_TOKEN       personal access token scoped to the base
//                        (data.records:read + data.records:write).
//   AIRTABLE_BASE_ID     optional override of the default base below.

import { timingSafeEqual, createHash } from "node:crypto";

export const config = { path: "/api/properties-data" };

const API = () => process.env.AIRTABLE_API_URL || "https://api.airtable.com";
const BASE = () => process.env.AIRTABLE_BASE_ID || "appgNkAc7lFFUi086";
const MAX_BYTES = 512 * 1024;
const T_PROPS = "Properties";
const T_AGENTS = "Agents";
const T_META = "Meta";
const STATUS_UP = { active: "Active", paused: "Paused", error: "Error", idle: "Idle" };
const STATUS_DOWN = { Active: "active", Paused: "paused", Error: "error", Idle: "idle" };

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

async function at(path, init = {}) {
  const doFetch = () =>
    fetch(`${API()}/v0/${BASE()}/${path}`, {
      ...init,
      headers: {
        Authorization: `Bearer ${process.env.AIRTABLE_TOKEN}`,
        "Content-Type": "application/json",
        ...(init.headers || {}),
      },
    });
  let res = await doFetch();
  if (res.status === 429) {
    await new Promise((r) => setTimeout(r, 1200));
    res = await doFetch();
  }
  if (!res.ok) {
    const detail = (await res.text()).slice(0, 300);
    throw new Error(`Airtable ${init.method || "GET"} ${path.split("?")[0]} -> ${res.status}: ${detail}`);
  }
  return res.json();
}

async function listAll(table) {
  const records = [];
  let offset;
  do {
    const q = "?pageSize=100" + (offset ? `&offset=${encodeURIComponent(offset)}` : "");
    const page = await at(encodeURIComponent(table) + q);
    records.push(...page.records);
    offset = page.offset;
  } while (offset);
  return records;
}

const chunk = (arr, n) => {
  const out = [];
  for (let i = 0; i < arr.length; i += n) out.push(arr.slice(i, i + n));
  return out;
};

// Upsert records merged on App ID; returns Map of App ID -> Airtable record id.
async function upsertByAppId(table, records) {
  const ids = new Map();
  for (const batch of chunk(records, 10)) {
    const res = await at(encodeURIComponent(table), {
      method: "PATCH",
      body: JSON.stringify({
        performUpsert: { fieldsToMergeOn: ["App ID"] },
        typecast: true,
        records: batch,
      }),
    });
    for (const rec of res.records) ids.set(rec.fields["App ID"], rec.id);
  }
  return ids;
}

async function deleteRecords(table, recordIds) {
  for (const batch of chunk(recordIds, 10)) {
    const q = batch.map((id) => "records[]=" + encodeURIComponent(id)).join("&");
    await at(encodeURIComponent(table) + "?" + q, { method: "DELETE" });
  }
}

// Rows created by hand in Airtable have no App ID; adopt the record id as
// their App ID so app pushes merge into them instead of duplicating.
async function backfillAppIds(table, records) {
  const missing = records.filter((r) => !r.fields["App ID"]);
  for (const batch of chunk(missing, 10)) {
    await at(encodeURIComponent(table), {
      method: "PATCH",
      body: JSON.stringify({
        records: batch.map((r) => ({ id: r.id, fields: { "App ID": r.id } })),
      }),
    });
    batch.forEach((r) => (r.fields["App ID"] = r.id));
  }
}

const byOrder = (a, b) =>
  (a.fields["Order"] ?? 1e9) - (b.fields["Order"] ?? 1e9) ||
  String(a.fields["Name"] || "").localeCompare(String(b.fields["Name"] || ""));

async function handleGet() {
  const [propRecs, agentRecs, metaRecs] = await Promise.all([
    listAll(T_PROPS),
    listAll(T_AGENTS),
    listAll(T_META),
  ]);
  await backfillAppIds(T_PROPS, propRecs);
  await backfillAppIds(T_AGENTS, agentRecs);

  const properties = propRecs.sort(byOrder).map((r) => ({
    id: r.fields["App ID"],
    name: String(r.fields["Name"] || "").trim() || "(unnamed)",
    url: r.fields["URL"] || "",
    notes: r.fields["Notes"] || "",
    agents: [],
  }));
  const byRecId = new Map(propRecs.map((r, i) => [r.id, properties[i]]));

  for (const r of agentRecs.sort(byOrder)) {
    const parent = byRecId.get((r.fields["Property"] || [])[0]);
    if (!parent) continue; // agent with no property link is invisible to the app
    parent.agents.push({
      id: r.fields["App ID"],
      name: String(r.fields["Name"] || "").trim() || "(unnamed)",
      role: r.fields["Role"] || "",
      status: STATUS_DOWN[r.fields["Status"]] || "idle",
      lastRun: r.fields["Last Run At"]
        ? {
            at: new Date(r.fields["Last Run At"]).toISOString(),
            outcome: r.fields["Last Run Outcome"] === "Failure" ? "failure" : "success",
            note: r.fields["Last Run Note"] || "",
          }
        : null,
    });
  }

  const meta = metaRecs.find((r) => r.fields["Key"] === "updatedAt");
  return json(
    { version: 1, updatedAt: meta ? meta.fields["Value"] || null : null, properties },
    200
  );
}

async function handlePut(doc) {
  const [propRecs, agentRecs] = await Promise.all([listAll(T_PROPS), listAll(T_AGENTS)]);

  const propRows = doc.properties.map((p, i) => ({
    fields: {
      "App ID": p.id,
      Name: p.name,
      URL: p.url || null,
      Notes: p.notes || "",
      Order: i,
    },
  }));
  const propIds = await upsertByAppId(T_PROPS, propRows);

  const agentRows = [];
  for (const p of doc.properties) {
    p.agents.forEach((a, i) => {
      agentRows.push({
        fields: {
          "App ID": a.id,
          Name: a.name,
          Role: a.role || "",
          Status: STATUS_UP[a.status] || "Idle",
          "Last Run At": a.lastRun ? a.lastRun.at : null,
          "Last Run Outcome": a.lastRun ? (a.lastRun.outcome === "failure" ? "Failure" : "Success") : null,
          "Last Run Note": a.lastRun ? a.lastRun.note || "" : "",
          Property: propIds.has(p.id) ? [propIds.get(p.id)] : [],
          Order: i,
        },
      });
    });
  }
  await upsertByAppId(T_AGENTS, agentRows);

  const keepProps = new Set(doc.properties.map((p) => p.id));
  const keepAgents = new Set(doc.properties.flatMap((p) => p.agents.map((a) => a.id)));
  // Delete agents first so no row ever points at a deleted property.
  await deleteRecords(
    T_AGENTS,
    agentRecs.filter((r) => !keepAgents.has(r.fields["App ID"] || r.id)).map((r) => r.id)
  );
  await deleteRecords(
    T_PROPS,
    propRecs.filter((r) => !keepProps.has(r.fields["App ID"] || r.id)).map((r) => r.id)
  );

  const updatedAt = typeof doc.updatedAt === "string" ? doc.updatedAt : new Date().toISOString();
  await at(encodeURIComponent(T_META), {
    method: "PATCH",
    body: JSON.stringify({
      performUpsert: { fieldsToMergeOn: ["Key"] },
      records: [{ fields: { Key: "updatedAt", Value: updatedAt } }],
    }),
  });

  return json({ ok: true, updatedAt }, 200);
}

export default async (req) => {
  const expected = process.env.PROPERTIES_SYNC_KEY;
  if (!expected || !process.env.AIRTABLE_TOKEN) {
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
      return await handlePut(doc);
    }

    return json({ error: "method not allowed" }, 405);
  } catch (err) {
    console.error("properties-data:", err);
    return json({ error: "storage backend error" }, 502);
  }
};
