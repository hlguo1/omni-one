/**
 * TS SDK demo — mirrors examples/sdk_demo.py for the TypeScript client.
 *
 * Default: OFFLINE (no network). Uses a mocked fetch that replays a golden
 * close bundle (seed 42) so `node examples/sdk_ts_demo.mjs` works anywhere.
 *
 * Live mode: --live [--base http://localhost:5003]
 *   Requires sdks/ts built (npm run build) OR tsx; imports the built ESM.
 *
 * Usage:
 *   node examples/sdk_ts_demo.mjs            # offline, mocked fetch
 *   node examples/sdk_ts_demo.mjs --live     # hits localhost:5003
 */
import { readFileSync, existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const args = new Set(process.argv.slice(2));
const LIVE = args.has("--live");
const baseIdx = process.argv.indexOf("--base");
const BASE = baseIdx >= 0 ? process.argv[baseIdx + 1] : "http://localhost:5003";

function goldenClose() {
  return {
    date: "2026-10-11",
    shop: "our shop",
    headline: "Profit $169.09 (61.7%) · $102.75 at risk in 3 angry messages · 1 reorder(s) TODAY",
    kpis: {
      gmv: 274.0, fees: 10.02, shipping: 16.0, net: 247.98, cogs: 78.89,
      true_profit: 169.09, margin_pct: 61.7, orders: 8, aov: 34.25,
      best_seller: { product: "Tote Bag Handmade", qty: 5 },
      money_at_risk_usd: 102.75,
    },
    do_today: ["Reply to 3 message(s)", "Reorder Tote Bag Handmade x10", "Plug leak"],
    reorder_sheet: [
      {
        product: "Tote Bag Handmade", on_hand: 2, sold_7d: 6, daily_velocity: 0.86,
        days_left: 2.33, reorder_qty: 10, cover_days: 14, supplier: "Acme Textiles",
        urgency: "ORDER TODAY", citation: "[inventory.csv:2] Tote Bag Handmade on_hand=2",
      },
    ],
    dead_stock_note: [],
    reply_queue: [
      {
        channel: "dm", customer: "Alice", summary: "Alice: Hi! My tote bag hasn't arrived yet",
        draft: "Hi Alice! I'm really sorry — checking tracking now. I'll update you within 2 hours. Thanks!",
        citation: "[instagram_dm.txt:1] Alice late delivery", priority: "P0-reply-in-2h",
      },
    ],
    money_leaks: [], listing_fixes: [],
    po_draft: "Subject: Reorder request — Acme Textiles\n\nPlease send Tote Bag Handmade x10.",
    citations: "every number cites [file:line]; audit via /seller/operations",
    free: true, offline: true,
  };
}

function mockFetchFactory() {
  const calls = [];
  const fetchFn = async (url, init = {}) => {
    calls.push({ url: String(url), headers: { ...(init.headers ?? {}) } });
    const path = String(url);
    const json = (obj) => ({ ok: true, status: 200, text: async () => JSON.stringify(obj) });
    if (path.endsWith("/health")) return json({ status: "alive", mode: "local", service: "omni-one" });
    if (path.includes("/seller/close")) return json(goldenClose());
    if (path.includes("/seller/briefing")) {
      const c = goldenClose();
      return json({ kpis: c.kpis, alerts: [], actions: c.do_today, stockout_risk: [] });
    }
    if (path.includes("/scenarios/run")) return json({ total: 12, decisions: [] });
    return json({});
  };
  return { fetchFn, calls };
}

if (!LIVE) {
  // ---- Offline demo (mocked fetch, no network) ----
  const { fetchFn, calls } = mockFetchFactory();
  const res = await fetchFn(`${BASE}/api/v1/seller/close`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-API-Key": "demo-key" },
    body: JSON.stringify({ demo: true }),
  });
  const close = JSON.parse(await res.text());
  console.log("== offline (mocked fetch) ==");
  console.log("headline:", close.headline);
  console.log("kpis.true_profit:", close.kpis.true_profit);
  console.log("kpis.money_at_risk_usd:", close.kpis.money_at_risk_usd);
  console.log("reorder[0]:", close.reorder_sheet[0].product, "x" + close.reorder_sheet[0].reorder_qty,
    `[${close.reorder_sheet[0].citation}]`);
  console.log("reply[0] draft:", close.reply_queue[0].draft.slice(0, 80) + "...");
  console.log("po_draft:", close.po_draft.split("\n")[0]);
  console.log(`(mocked ${calls.length} call(s), X-API-Key sent: ${calls[0].headers["X-API-Key"]})`);
  console.log("citations preserved:", close.reorder_sheet[0].citation.includes("inventory.csv"));
} else {
  // ---- Live demo (built SDK against a running server) ----
  const built = join(HERE, "..", "sdks", "ts", "dist", "esm", "index.js");
  if (!existsSync(built)) {
    console.error(`live mode needs a build: (cd sdks/ts && npm install && npm run build) — missing ${built}`);
    process.exit(2);
  }
  const { OmniOneClient } = await import(built);
  const apiKey = process.env.OMNI_ONE_API_KEY;
  for (const base of [BASE, ""]) {
    try {
      const c = base ? new OmniOneClient({ baseUrl: base, apiKey }) : OmniOneClient.local({ apiKey });
      console.log(`== ${base || "local-preset"} ==`);
      console.log("health:", await c.health());
      console.log("kpis:", (await c.briefingDemo()).kpis);
      console.log("scenarios total:", (await c.scenariosRun()).total);
      console.log("close headline:", (await c.close({ demo: true })).headline);
      break;
    } catch (e) {
      console.log(`${base || "local"} failed: ${e.message}`);
    }
  }
  void readFileSync; // keep import used in offline path readers
}
