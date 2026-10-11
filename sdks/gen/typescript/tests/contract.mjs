// Contract tests for sdks/gen/typescript/client_generated.ts (WAVE3-L).
//
// Node stdlib only (node:fs, node:path, node:url): reads the GENERATED
// TypeScript client as text and asserts the contract without compiling it:
//   - 18 async methods (one per snapshot route)
//   - 6 domain interfaces (KPIs/ReorderLine/ReplyItem/Briefing/ScenarioDecision/CloseBundle)
//   - fetch + AbortController + retry plumbing present
//   - version pin 1.1.0
//
// Run from the repo root:
//
//   node sdks/gen/typescript/tests/contract.mjs
//
// Exit code is 0 on green, 1 on any contract violation (CI-friendly).

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const CLIENT = path.resolve(HERE, "..", "client_generated.ts");

let text = "";
try {
  text = readFileSync(CLIENT, "utf8");
} catch (err) {
  console.error(`FAIL: cannot read GENERATED client at ${CLIENT}: ${err.message}`);
  process.exit(1);
}

// ---------------------------------------------------------------------------
// Tiny assertion harness (no deps): counts passes, prints failures, exits.
// ---------------------------------------------------------------------------

let passed = 0;
let failed = 0;
const failures = [];

function ok(cond, label, detail = "") {
  if (cond) {
    passed += 1;
    console.log(`ok - ${label}`);
  } else {
    failed += 1;
    failures.push(label);
    console.log(`FAIL - ${label}${detail ? ` :: ${detail}` : ""}`);
  }
}

function countOf(re) {
  const m = text.match(re);
  return m ? m.length : 0;
}

// ---------------------------------------------------------------------------
// 1. GENERATED header + version pin 1.1.0 (tracks openapi_snapshot.json).
// ---------------------------------------------------------------------------

const firstLine = text.split("\n")[0] || "";
ok(
  firstLine.includes("// GENERATED") && firstLine.includes("openapi_snapshot.json"),
  "header: GENERATED from openapi_snapshot.json on line 1",
  firstLine.slice(0, 80),
);
ok(
  text.includes("do not hand-edit"),
  "header: do-not-hand-edit marker present",
);
ok(
  text.includes('GENERATED_VERSION = "1.1.0"'),
  'version: GENERATED_VERSION == "1.1.0"',
);
ok(
  text.includes("1.1.0") && text.includes("omni-one"),
  "version: snapshot title/version prose present",
);

// ---------------------------------------------------------------------------
// 2. Eighteen async methods (snapshot routes 1:1, snake_case like python).
// ---------------------------------------------------------------------------

const EXPECTED_METHODS = [
  // [tsMethod, httpVerb, snapshotPath]
  ["seller_close", "POST", "/api/v1/seller/close"],
  ["seller_close_csv", "GET", "/api/v1/seller/close.csv"],
  ["seller_briefing", "POST", "/api/v1/seller/briefing"],
  ["seller_operations", "POST", "/api/v1/seller/operations"],
  ["seller_scenarios_list", "GET", "/api/v1/seller/scenarios"],
  ["seller_scenarios_run", "POST", "/api/v1/seller/scenarios/run"],
  ["seller_export_csv", "GET", "/api/v1/seller/export.csv"],
  ["seller_photo", "POST", "/api/v1/seller/photo"],
  ["vision_analyze", "POST", "/api/v1/vision/analyze"],
  ["vision_demo", "GET", "/api/v1/vision/demo"],
  ["analyze", "POST", "/api/v1/analyze"],
  ["synthesize", "POST", "/api/v1/synthesize"],
  ["revenue_health", "POST", "/api/v1/revenue/health"],
  ["micro_briefing", "POST", "/api/v1/micro/briefing"],
  ["get_metrics", "GET", "/api/v1/metrics"],
  ["list_models", "GET", "/api/v1/models"],
  ["health", "GET", "/health"],
  ["openapi_tags", "GET", "/api/v1/openapi-tags"],
];

ok(EXPECTED_METHODS.length === 18, "contract table holds 18 methods");

for (const [name] of EXPECTED_METHODS) {
  ok(
    text.includes(`async ${name}(`),
    `method: async ${name}( defined`,
  );
}

const asyncCount = countOf(/async [a-z_0-9]+\(/g);
ok(
  asyncCount >= 18,
  `methods: >= 18 async definitions (found ${asyncCount})`,
);

// Each method cites its snapshot path in a comment (traceability).
for (const [name, , snapPath] of EXPECTED_METHODS) {
  const idx = text.indexOf(`async ${name}(`) ;
  const window = idx >= 0 ? text.slice(Math.max(0, idx - 1500), idx) : "";
  ok(
    idx >= 0 && window.includes(snapPath),
    `method docs: ${name} cites ${snapPath}`,
  );
}

// ---------------------------------------------------------------------------
// 3. Six domain interfaces (citation-preserving typed wrappers).
// ---------------------------------------------------------------------------

const EXPECTED_INTERFACES = [
  "KPIs",
  "ReorderLine",
  "ReplyItem",
  "Briefing",
  "ScenarioDecision",
  "CloseBundle",
];

for (const name of EXPECTED_INTERFACES) {
  ok(
    text.includes(`interface ${name} `) || text.includes(`interface ${name}{`) || text.includes(`interface ${name}\n`),
    `interface: ${name} declared`,
  );
}

// KPI ledger core: gmv / true_profit / money_at_risk_usd must be typed.
for (const field of ["gmv", "true_profit", "money_at_risk_usd"]) {
  ok(text.includes(field), `KPIs field: ${field} present`);
}

// Contract vocabulary across interfaces: product/citation/reply_queue/draft.
for (const field of ["product", "citation", "reply_queue", "draft", "po_draft", "headline", "kpis"]) {
  ok(text.includes(field), `contract field: ${field} present`);
}

// The 8 request-body interfaces travel with POST routes.
const EXPECTED_REQUESTS = [
  "CloseRequest",
  "BriefingRequest",
  "OperationsRequest",
  "ScenariosRunRequest",
  "AnalyzeRequest",
  "SynthesizeRequest",
  "RevenueHealthRequest",
  "MicroBriefingRequest",
];
for (const name of EXPECTED_REQUESTS) {
  ok(text.includes(`interface ${name}`), `request interface: ${name} declared`);
}

// Every interface keeps raw + citations (never drop [file:line]).
ok(countOf(/citations\?: string\[\]/g) >= 6, "citations: string[] on all 6+ interfaces");
ok(countOf(/raw\?: Record<string, unknown>/g) >= 6, "raw passthrough on all 6+ interfaces");

// ---------------------------------------------------------------------------
// 4. fetch + AbortController + retry plumbing (no new deps).
// ---------------------------------------------------------------------------

ok(text.includes("fetch("), "http: fetch( used for transport");
ok(text.includes("AbortController"), "timeout: AbortController present");
ok(
  text.includes("DEFAULT_TIMEOUT_MS") && text.includes("30000"),
  "timeout: DEFAULT_TIMEOUT_MS 30000 (30s parity with py/go)",
);
ok(
  text.includes("X-API-Key"),
  "auth: X-API-Key header wired",
);
ok(
  /retr/i.test(text) && text.includes("DEFAULT_RETRIES"),
  "retry: DEFAULT_RETRIES plumbing present",
);
ok(
  text.includes("DEFAULT_BACKOFF_MS") && text.includes("500"),
  "retry: DEFAULT_BACKOFF_MS 500 (exponential backoff)",
);
ok(
  text.includes("429") && text.includes("500"),
  "retry: 429/5xx retry set documented",
);
ok(
  !text.includes("from \"axios\"") && !text.includes("from 'axios'") && !text.includes('require("axios")'),
  "deps: no axios import (fetch-only)",
);
ok(
  !text.includes("node-fetch"),
  "deps: no node-fetch import (global fetch only)",
);

// ---------------------------------------------------------------------------
// 5. Per-method curl examples + brace balance (parse health).
// ---------------------------------------------------------------------------

const curlCount = countOf(/curl -s/g);
ok(curlCount >= 18, `docs: >= 18 curl examples (found ${curlCount})`);

const opens = countOf(/\{/g);
const closes = countOf(/\}/g);
ok(opens === closes && opens > 0, `syntax: braces balanced (open=${opens} close=${closes})`);

// Client class + options surface (baseUrl param only, no hardcoded origins).
ok(text.includes("class OmniOneGeneratedClient"), "client: OmniOneGeneratedClient class present");
ok(text.includes("baseUrl"), "client: baseUrl option (param-driven URLs)");
ok(
  text.includes("DEFAULT_BASE_URL") && text.includes("http://localhost:5003"),
  "client: DEFAULT_BASE_URL localhost default",
);

// Golden numbers documented (true_profit 169.09 anchors the demo story).
ok(text.includes("169.09"), "golden: true_profit 169.09 documented");
ok(text.includes("true_profit<=gmv") || text.includes("true_profit <= gmv"), "invariant: true_profit<=gmv documented");

// ---------------------------------------------------------------------------
// 6. No hardcoded localhost origins in executable positions.
//    Allowed: DEFAULT_BASE_URL definition, curl examples, prose comments.
// ---------------------------------------------------------------------------

function localhostViolations() {
  const bad = [];
  const lines = text.split("\n");
  let inBlock = false;
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const trimmed = line.trim();
    if (trimmed.startsWith("/*")) inBlock = true;
    const isComment =
      inBlock || trimmed.startsWith("//") || trimmed.startsWith("*") || trimmed.startsWith("/*");
    if (trimmed.includes("*/")) inBlock = false;
    if (!line.includes("localhost") && !line.includes("127.0.0.1")) continue;
    if (line.includes("DEFAULT_BASE_URL")) continue; // single allowed definition
    if (line.includes("curl")) continue; // shell examples, never executed
    if (isComment) continue; // prose/docs (incl. Go/Python usage snippets)
    if (/["']http:\/\/(localhost|127\.0\.0\.1)/.test(line)) {
      // String literal with an origin outside defaults/docs: only allowed
      // when it is the documented local-dev example assignment.
      if (!line.includes("baseUrl") && !line.includes("base_url")) {
        bad.push(`${i + 1}: ${trimmed.slice(0, 100)}`);
      }
    }
  }
  return bad;
}

const violations = localhostViolations();
ok(violations.length === 0, "urls: no hardcoded localhost origins in code", violations.join(" | "));

// Method bodies must route through the baseUrl member (param-driven).
let missingBase = [];
for (const [name] of EXPECTED_METHODS) {
  const idx = text.indexOf(`async ${name}(`);
  if (idx < 0) continue;
  // Body starts at the first "{" AFTER the return type (signatures carry
  // inline object types like { fileBytes?: ... }, which must be skipped).
  const retIdx = text.indexOf("Promise<", idx);
  const brace = text.indexOf("{", retIdx >= 0 ? retIdx : idx);
  let depth = 0;
  let end = -1;
  for (let i = brace; i < text.length && i < brace + 6000; i++) {
    if (text[i] === "{") depth++;
    if (text[i] === "}") {
      depth--;
      if (depth === 0) {
        end = i;
        break;
      }
    }
  }
  const body = end > 0 ? text.slice(brace, end) : "";
  if (!body.includes("baseUrl") && !body.includes("buildUrl") && !body.includes("doFetch")) {
    missingBase.push(name);
  }
}
ok(missingBase.length === 0, "urls: every method routes via baseUrl/buildUrl/doFetch", missingBase.join(","));

// ---------------------------------------------------------------------------
// Summary (machine-readable tail for CI logs).
// ---------------------------------------------------------------------------

console.log("---");
console.log(`contract: ${passed} passed, ${failed} failed, ${EXPECTED_METHODS.length} methods, ${EXPECTED_INTERFACES.length} interfaces`);
if (failed > 0) {
  console.log(`missing: ${failures.join("; ")}`);
  process.exit(1);
}
console.log("CONTRACT PASS: typescript client covers 18/18 routes, 6/6 interfaces, version 1.1.0.");
