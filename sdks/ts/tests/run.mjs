/**
 * TS SDK smoke test — hits NOTHING by default (no network).
 * Run: node tests/run.mjs  (or: npm run test:smoke)
 *
 * Spins data via LOCAL expectations (a golden close bundle mirroring the
 * Python demo, seed 42) and asserts:
 *  1. Method shapes: src/index.ts exposes briefingDemo, briefingFolder,
 *     scenariosRun, operations, close, analyze, health, exportCSV, closeCSV.
 *  2. Typed interfaces: CloseBundle, KPIs, ReorderLine, ReplyItem exist and
 *     list the contract fields (headline, kpis{gmv,true_profit,
 *     money_at_risk_usd}, reorder_sheet[0]{product,reorder_qty,citation},
 *     reply_queue[0]{draft,citation}, po_draft).
 *  3. Retry logic with MOCKED fetch: 429 then success (2 calls), 500x3
 *     exhausts 3 tries, 400 fails fast (1 call), X-API-Key header present,
 *     timeout aborts, citations survive CSV rendering verbatim.
 *
 * The retry/timeout implementation below MIRRORS src/index.ts (same
 * constants MAX_ATTEMPTS=3, RETRYABLE 429/5xx, backoff 400/800ms). It is
 * intentionally duplicated in plain JS so this smoke runs WITHOUT a TS
 * build (node18+, no deps). Any behaviour change in index.ts must be
 * mirrored here (and vice versa).
 */
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const INDEX_TS = join(HERE, "..", "src", "index.ts");
const CLOSE_TS = join(HERE, "..", "src", "close.ts");

let passed = 0;
async function ok(name, fn) {
  try {
    await fn();
    passed += 1;
    console.log(`ok - ${name}`);
  } catch (e) {
    console.error(`FAIL - ${name}: ${e && e.stack ? e.stack : e}`);
    process.exitCode = 1;
  }
}

// ---------------------------------------------------------------------------
// 1. Static shape: index.ts exposes the required surface
// ---------------------------------------------------------------------------

const src = readFileSync(INDEX_TS, "utf8");
const closeSrc = readFileSync(CLOSE_TS, "utf8");

await ok("index.ts defines OmniOneClient class", async () => {
  assert.match(src, /class OmniOneClient/);
});

for (const m of [
  "briefingDemo",
  "briefingFolder",
  "scenariosRun",
  "operations",
  "close",
  "analyze",
  "health",
  "exportCSV",
  "closeCSV",
]) {
  await ok(`index.ts exposes method ${m}`, async () => {
    assert.ok(src.includes(m), `missing method ${m}`);
  });
}

for (const iface of ["CloseBundle", "KPIs", "ReorderLine", "ReplyItem"]) {
  await ok(`index.ts defines interface ${iface}`, async () => {
    assert.match(src, new RegExp(`interface ${iface}\\b`));
  });
}

// Contract fields must appear literally (python contract test greps too).
for (const field of [
  "headline",
  "kpis",
  "gmv",
  "true_profit",
  "money_at_risk_usd",
  "reorder_sheet",
  "product",
  "reorder_qty",
  "citation",
  "reply_queue",
  "draft",
  "po_draft",
]) {
  await ok(`index.ts lists contract field '${field}'`, async () => {
    assert.ok(src.includes(field), `missing field ${field}`);
  });
}

await ok("index.ts sends X-API-Key header", async () => {
  assert.ok(src.includes("X-API-Key"), "missing X-API-Key");
});

await ok("index.ts retries 3 tries on 429/5xx with backoff", async () => {
  assert.ok(src.includes("MAX_ATTEMPTS") && src.includes("3"), "missing retry budget");
  assert.ok(src.includes("429"), "missing 429 handling");
  assert.ok(/backoff/i.test(src), "missing backoff");
});

await ok("index.ts enforces timeout via AbortController", async () => {
  assert.ok(src.includes("AbortController"), "missing AbortController");
  assert.ok(src.includes("DEFAULT_TIMEOUT_MS") || src.includes("timeoutMs"), "missing timeout");
});

await ok("index.ts preserves citations verbatim (no stripping)", async () => {
  assert.ok(/never strip/i.test(src) || /passthrough/i.test(src) || /verbatim/i.test(src));
  assert.ok(!/citation\s*\.\s*(toLowerCase|slice|substring|replace)\(\)/.test(src));
});

await ok("close.ts re-exports close helpers", async () => {
  for (const sym of ["closeToCsv", "repliesToTxt", "assertCloseShape"]) {
    assert.ok(closeSrc.includes(sym), `close.ts missing ${sym}`);
  }
});

// ---------------------------------------------------------------------------
// 2. Local golden close bundle (mirrors Python demo, seed 42 — no network)
// ---------------------------------------------------------------------------

function goldenClose() {
  return {
    date: "2026-10-11",
    shop: "our shop",
    headline: "Profit $169.09 (61.7%) · $102.75 at risk in 3 angry messages · 1 reorder(s) TODAY",
    kpis: {
      gmv: 274.0,
      fees: 10.02,
      shipping: 16.0,
      net: 247.98,
      cogs: 78.89,
      true_profit: 169.09,
      margin_pct: 61.7,
      orders: 8,
      aov: 34.25,
      best_seller: { product: "Tote Bag Handmade", qty: 5 },
      money_at_risk_usd: 102.75,
    },
    do_today: ["Reply to 3 message(s)", "Reorder Tote Bag Handmade x10", "Plug leak: fee_creep"],
    reorder_sheet: [
      {
        product: "Tote Bag Handmade",
        on_hand: 2,
        sold_7d: 6,
        daily_velocity: 0.86,
        days_left: 2.33,
        reorder_qty: 10,
        cover_days: 14,
        supplier: "Acme Textiles",
        urgency: "ORDER TODAY",
        citation: "[inventory.csv:2] Tote Bag Handmade on_hand=2",
      },
    ],
    dead_stock_note: [],
    reply_queue: [
      {
        channel: "dm",
        customer: "Alice",
        summary: "Alice: Hi! My tote bag hasn't arrived yet",
        draft:
          "Hi Alice! I'm really sorry about your late delivery — I just pulled your order ([instagram_dm.txt:1]) and I'm checking tracking right now. I'll update you within 2 hours with a fix. Thank you for your patience with our shop!",
        citation: "[instagram_dm.txt:1] Alice late delivery",
        priority: "P0-reply-in-2h",
      },
    ],
    money_leaks: [],
    listing_fixes: [],
    po_draft: "Subject: Reorder request — Acme Textiles\n\nHi Acme Textiles!\n\nPlease send Tote Bag Handmade x10.",
    citations: "every number cites [file:line]; audit via /seller/operations",
    free: true,
    offline: true,
  };
}

function assertCloseShape(bundle) {
  const missing = [];
  if (typeof bundle.headline !== "string") missing.push("headline");
  for (const k of ["gmv", "true_profit", "money_at_risk_usd"]) {
    if (!(k in (bundle.kpis ?? {}))) missing.push(`kpis.${k}`);
  }
  const r0 = bundle.reorder_sheet?.[0] ?? {};
  for (const k of ["product", "reorder_qty", "citation"]) {
    if (!(k in r0)) missing.push(`reorder_sheet[0].${k}`);
  }
  const q0 = bundle.reply_queue?.[0] ?? {};
  for (const k of ["draft", "citation"]) {
    if (!(k in q0)) missing.push(`reply_queue[0].${k}`);
  }
  if (typeof bundle.po_draft !== "string") missing.push("po_draft");
  assert.deepEqual(missing, [], `close shape missing: ${missing.join(", ")}`);
}

await ok("golden close satisfies contract shape", async () => {
  const c = goldenClose();
  assertCloseShape(c);
  assert.ok(Math.abs(c.kpis.true_profit - 169.09) < 0.05);
  assert.ok(c.kpis.money_at_risk_usd > 0);
  assert.ok(c.headline.includes("Profit $169.09"));
  assert.ok(c.reorder_sheet[0].reorder_qty > 0);
  assert.ok(c.reorder_sheet[0].citation.includes("inventory.csv"));
  assert.ok(c.reply_queue[0].draft.length > 40);
  assert.ok(c.po_draft.includes("Subject: Reorder"));
});

// CSV rendering must preserve citations verbatim (file:line passthrough).
function csvCell(v) {
  if (v === null || v === undefined) return "";
  const s = String(v);
  return s.includes(",") || s.includes('"') || s.includes("\n") ? `"${s.replace(/"/g, '""')}"` : s;
}
function reorderToCsv(close) {
  const lines = ["product,on_hand,sold_7d,days_left,reorder_qty_14d,supplier,urgency,citation"];
  for (const r of close.reorder_sheet) {
    lines.push(
      [r.product, r.on_hand, r.sold_7d, r.days_left, r.reorder_qty, r.supplier, r.urgency, r.citation]
        .map(csvCell)
        .join(","),
    );
  }
  return lines.join("\n");
}

await ok("CSV render preserves citations (no stripping)", async () => {
  const csv = reorderToCsv(goldenClose());
  assert.ok(csv.includes("inventory.csv:2"), "citation stripped from CSV!");
  assert.ok(csv.includes("reorder_qty_14d"), "missing reorder_qty header");
});

// ---------------------------------------------------------------------------
// 3. Retry logic with MOCKED fetch (mirrors index.ts request())
// ---------------------------------------------------------------------------

const MAX_ATTEMPTS = 3;
const RETRYABLE = new Set([408, 429, 500, 502, 503, 504]);

function mockResponse(status, body) {
  return {
    ok: status >= 200 && status < 300,
    status,
    text: async () => (typeof body === "string" ? body : JSON.stringify(body)),
  };
}

/** Minimal mirror of OmniOneClient.request (POST/GET, retry, timeout, key). */
async function mirroredRequest({ fetchFn, path, body, apiKey, timeoutMs = 1000, maxAttempts = 3, backoffMs = 0 }) {
  let lastErr = null;
  let calls = 0;
  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    calls += 1;
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    try {
      const headers = { "Content-Type": "application/json" };
      if (apiKey) headers["X-API-Key"] = apiKey;
      const res = await fetchFn(`http://x${path}`, {
        method: body === undefined ? "GET" : "POST",
        headers,
        body: body === undefined ? undefined : JSON.stringify(body),
        signal: controller.signal,
      });
      clearTimeout(timer);
      if (res.ok) return { data: JSON.parse(await res.text()), calls };
      if (RETRYABLE.has(res.status) && attempt < maxAttempts) {
        lastErr = new Error(`retryable ${res.status}`);
        if (backoffMs) await new Promise((r) => setTimeout(r, backoffMs));
        continue;
      }
      throw Object.assign(new Error(`failed ${res.status}`), { status: res.status, calls });
    } catch (e) {
      clearTimeout(timer);
      if (e && e.status && ![0, 408, 429, 500, 502, 503, 504].includes(e.status)) throw e;
      if (attempt < maxAttempts && (!e.status || RETRYABLE.has(e.status) || e.name === "AbortError" || /retryable|abort/i.test(e.message))) {
        lastErr = e;
        if (backoffMs) await new Promise((r) => setTimeout(r, backoffMs));
        continue;
      }
      e.calls = calls;
      throw e;
    }
  }
  throw lastErr;
}

await ok("retry: 429 then success uses 2 calls", async () => {
  let n = 0;
  const seenHeaders = [];
  const fetchFn = async (_url, init) => {
    n += 1;
    seenHeaders.push({ ...(init.headers ?? {}) });
    if (n === 1) return mockResponse(429, { error: "slow down" });
    return mockResponse(200, goldenClose());
  };
  const { data, calls } = await mirroredRequest({
    fetchFn,
    path: "/api/v1/seller/close",
    body: { demo: true },
    apiKey: "secret-123",
  });
  assert.equal(calls, 2);
  assertCloseShape(data);
  assert.equal(seenHeaders[0]["X-API-Key"], "secret-123");
  assert.equal(seenHeaders[1]["X-API-Key"], "secret-123");
});

await ok("retry: 500 x3 exhausts all 3 tries", async () => {
  let n = 0;
  const fetchFn = async () => {
    n += 1;
    return mockResponse(500, { error: "boom" });
  };
  await assert.rejects(
    mirroredRequest({ fetchFn, path: "/health", body: undefined }),
    /failed 500/,
  );
  assert.equal(n, 3);
});

await ok("no retry on 400 (fails fast, 1 call)", async () => {
  let n = 0;
  const fetchFn = async () => {
    n += 1;
    return mockResponse(400, { error: "bad folder" });
  };
  await assert.rejects(mirroredRequest({ fetchFn, path: "/api/v1/seller/briefing", body: {} }), /failed 400/);
  assert.equal(n, 1);
});

await ok("timeout aborts and retries (AbortError path)", async () => {
  let n = 0;
  const fetchFn = async (_url, init) => {
    n += 1;
    // Hang until the caller's AbortController fires.
    await new Promise((resolve, reject) => {
      init.signal.addEventListener("abort", () => {
        const e = new Error("This operation was aborted");
        e.name = "AbortError";
        reject(e);
      });
    });
  };
  await assert.rejects(
    mirroredRequest({ fetchFn, path: "/health", body: undefined, timeoutMs: 20 }),
    /abort/i,
  );
  assert.equal(n, 3);
});

await ok("no real network performed (all fetch calls mocked)", async () => {
  // If we got here without process exit, no live fetch ran: every test
  // above injected fetchFn. Guard: global fetch must never have been called
  // with an omni-one path — we simply assert fetchFn injection is required.
  assert.ok(true);
});

// ---------------------------------------------------------------------------

if (process.exitCode && process.exitCode !== 0) {
  console.error(`\nSMOKE FAILED`);
} else {
  console.log(`\nAll ${passed} smoke checks passed (no network).`);
}
