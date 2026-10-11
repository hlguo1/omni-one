/**
 * Omni-One TypeScript SDK — local-first seller OS client.
 * =====================================================================
 * Fetch-based, works on node18+ and browsers. $0, offline-friendly.
 *
 * ```ts
 * import { OmniOneClient } from "@omni-one/sdk-ts";
 *
 * const client = new OmniOneClient({ baseUrl: "http://localhost:5003" });
 * const health = await client.health();            // { status: "alive", ... }
 * const briefing = await client.briefingDemo();    // GMV 274.00 / profit 169.09
 * const close = await client.close({ demo: true }); // CloseBundle (cited)
 * console.log(close.headline);                     // "Profit $169.09 ..."
 * console.log(close.kpis.true_profit);             // 169.09
 * console.log(close.kpis.money_at_risk_usd);       // > 0
 * console.log(close.reorder_sheet[0].citation);    // "inventory.csv:2" (verbatim)
 * ```
 *
 * DESIGN RULES (mirror the Python SDK in src/omni_one/client.py):
 *  - Retry with backoff: 3 tries total on 429 / 5xx, exponential backoff
 *    (400ms, 800ms) with jitter. Non-retryable 4xx throws immediately.
 *  - Timeout: per-request AbortController timeout (default 30s), surfaced
 *    as OmniOneTimeoutError.
 *  - Auth: apiKey header `X-API-Key` on every request when configured.
 *  - file:line passthrough: citation strings (e.g. "inventory.csv:2",
 *    "instagram_dm.txt:1") are NEVER stripped, lowercased, truncated, or
 *    re-mapped. JSON is parsed verbatim; helpers copy citations as-is.
 *    Tests assert citations still contain ".csv:" / ".txt:" after every
 *    transform (see tests/run.mjs).
 *  - ESM + CJS friendly: package.json dual exports (import + require),
 *    no node-only imports at module top-level (fetch is injected / global).
 *  - No dependencies: only the global fetch API (node18+ / browsers).
 *
 * CITATION CONTRACT (both SDKs must satisfy tests/unit/test_sdk_contract.py):
 *  CloseBundle fields: headline, kpis { gmv, true_profit, money_at_risk_usd },
 *  reorder_sheet[0] { product, reorder_qty, citation },
 *  reply_queue[0] { draft, citation }, po_draft.
 *  This file MUST keep those exact field names (the contract test greps for
 *  them). Do not rename without updating the Python + Go SDKs together.
 *
 * @packageDocumentation
 */

// ---------------------------------------------------------------------------
// Version + defaults
// ---------------------------------------------------------------------------

/** SDK version (mirrors package.json). */
export const SDK_VERSION = "1.1.0";

/** Default request timeout in milliseconds (30s, mirrors Python SDK). */
export const DEFAULT_TIMEOUT_MS = 30_000;

/** Max attempts per request (initial + 2 retries = 3 tries). */
export const MAX_ATTEMPTS = 3;

/** Base backoff in ms (attempt 1 -> 400ms, attempt 2 -> 800ms, + jitter). */
export const BASE_BACKOFF_MS = 400;

/** HTTP statuses worth retrying (429 + 5xx). */
export const RETRYABLE_STATUSES = new Set([408, 429, 500, 502, 503, 504]);

// ---------------------------------------------------------------------------
// Error types
// ---------------------------------------------------------------------------

/**
 * Base SDK error. Carries HTTP status + endpoint for debuggability.
 */
export class OmniOneError extends Error {
  /** HTTP status code (0 = network/timeout, no response). */
  readonly status: number;
  /** API path that failed (e.g. "/api/v1/seller/close"). */
  readonly path: string;
  /** How many attempts were made (1..MAX_ATTEMPTS). */
  readonly attempts: number;

  constructor(message: string, opts?: { status?: number; path?: string; attempts?: number }) {
    super(message);
    this.name = "OmniOneError";
    this.status = opts?.status ?? 0;
    this.path = opts?.path ?? "";
    this.attempts = opts?.attempts ?? 1;
  }
}

/**
 * Timeout error (AbortController fired before the server answered).
 */
export class OmniOneTimeoutError extends OmniOneError {
  /** Timeout budget in ms. */
  readonly timeoutMs: number;
  constructor(path: string, timeoutMs: number, attempts: number) {
    super(`omni-one request timed out after ${timeoutMs}ms (${path}, ${attempts} attempt(s))`, {
      status: 0,
      path,
      attempts,
    });
    this.name = "OmniOneTimeoutError";
    this.timeoutMs = timeoutMs;
  }
}

/**
 * Rate-limit error (HTTP 429 exhausted all retries).
 */
export class OmniOneRateLimitError extends OmniOneError {
  constructor(path: string, attempts: number) {
    super(`omni-one rate limited (429) after ${attempts} attempt(s): ${path}`, {
      status: 429,
      path,
      attempts,
    });
    this.name = "OmniOneRateLimitError";
  }
}

// ---------------------------------------------------------------------------
// Typed interfaces — the contract surface
// (FIELD NAMES ARE LOAD-BEARING: tests/unit/test_sdk_contract.py greps them)
// ---------------------------------------------------------------------------

/**
 * Best-seller summary inside KPIs.
 */
export interface BestSeller {
  /** Display name, verbatim (e.g. "Tote Bag Handmade"). */
  product: string;
  /** Units sold. */
  qty: number;
}

/**
 * KPIs — every dollar auditable to file:line via the bundle citations.
 *
 * Golden demo values (seed 42): gmv 274.00, true_profit 169.09,
 * money_at_risk_usd > 0, orders 8.
 */
export interface KPIs {
  /** Gross merchandise value (e.g. 274.00). */
  gmv: number;
  /** Marketplace fees. */
  fees: number;
  /** Shipping cost. */
  shipping: number;
  /** gmv - fees - shipping. */
  net: number;
  /** Cost of goods sold (from supplier invoices). */
  cogs: number;
  /** GOLDEN: net - cogs (e.g. 169.09). */
  true_profit: number;
  /** true_profit / gmv * 100 (e.g. 61.7). */
  margin_pct: number;
  /** Order count (golden: 8). */
  orders: number;
  /** Average order value. */
  aov: number;
  /** Best seller (product + qty). */
  best_seller: BestSeller;
  /** len(reply_queue) * aov — dollars that churn if you sleep. */
  money_at_risk_usd: number;
  /** Extra KPI keys are allowed (forward-compat). */
  [extra: string]: unknown;
}

/**
 * One briefing alert (severity + message + evidence file:line).
 */
export interface AlertItem {
  severity: string;
  message: string;
  evidence?: string[];
}

/**
 * One stockout-risk row in the briefing.
 */
export interface StockoutRow {
  product: string;
  on_hand: number;
  sold_7d: number;
  days_supply: number;
  citation: string;
}

/**
 * One at-risk message preview (DM / review snippet + citation).
 */
export interface AtRiskPreview {
  text: string;
  citation: string;
  source: string;
}

/**
 * Seller briefing bundle (briefingDemo / briefingFolder).
 */
export interface BriefingBundle {
  kpis: KPIs;
  alerts: AlertItem[];
  actions: string[];
  stockout_risk: StockoutRow[];
  at_risk_preview?: AtRiskPreview[];
  ingest_report?: Record<string, unknown>;
  [extra: string]: unknown;
}

/**
 * One ranked scenario decision.
 */
export interface ScenarioDecision {
  scenario?: string;
  scenario_id?: string;
  severity?: string;
  title?: string;
  evidence?: string[];
  action?: string;
  [extra: string]: unknown;
}

/**
 * Scenarios result (scenariosRun).
 */
export interface ScenariosResult {
  total: number;
  by_scenario?: Record<string, number>;
  decisions: ScenarioDecision[];
  ctx?: Record<string, unknown>;
  [extra: string]: unknown;
}

/**
 * Operations result (briefing KPIs + workshop stats + governance stats).
 */
export interface OperationsResult {
  briefing_kpis: KPIs;
  workshop: Record<string, unknown>;
  governance: Record<string, unknown>;
  [extra: string]: unknown;
}

/**
 * Generic analyze result.
 */
export interface AnalyzeResult {
  records_processed: number;
  metrics: Record<string, unknown>;
  [extra: string]: unknown;
}

/**
 * Health result.
 */
export interface HealthResult {
  status: string;
  mode?: string;
  service?: string;
  [extra: string]: unknown;
}

/**
 * ReorderLine — one row of the reorder sheet.
 *
 * CITATION RULE: `citation` (file:line, e.g. "inventory.csv:2") passes
 * through verbatim. Never strip / rewrite / truncate it.
 */
export interface ReorderLine {
  /** Display name, verbatim (e.g. "Tote Bag Handmade"). */
  product: string;
  /** Units on hand. */
  on_hand: number;
  /** Units sold in the last 7 days. */
  sold_7d: number;
  /** sold_7d / 7. */
  daily_velocity: number;
  /** on_hand / velocity (days of cover left). */
  days_left: number;
  /** ceil(velocity * 14 - on_hand), floored at 0. */
  reorder_qty: number;
  /** Cover window (14). */
  cover_days: number;
  /** Supplier name from inventory.csv (verbatim). */
  supplier: string;
  /** "ORDER TODAY" | "this week" | "watch". */
  urgency: string;
  /** file:line (e.g. "inventory.csv:2") — NEVER stripped. */
  citation: string;
  [extra: string]: unknown;
}

/**
 * ReplyItem — one copy-paste customer reply draft.
 *
 * CITATION RULE: `citation` + `draft` pass through verbatim so the owner
 * can audit which file:line each draft answers.
 */
export interface ReplyItem {
  /** "dm" | "review" | "scenario". */
  channel: string;
  /** Customer first name / handle. */
  customer: string;
  /** 120-char customer message snippet. */
  summary: string;
  /** Copy-paste draft (>40 chars, contains "2 hour" for DM urgents). */
  draft: string;
  /** file:line answered by this draft (e.g. "instagram_dm.txt:1"). */
  citation: string;
  /** "P0-reply-in-2h" | "P1-today". */
  priority: string;
  [extra: string]: unknown;
}

/**
 * Money leak with dollar amount + evidence.
 */
export interface MoneyLeak {
  leak: string;
  amount_usd: number | null;
  note: string;
  evidence: string;
  [extra: string]: unknown;
}

/**
 * Listing fix suggestion.
 */
export interface ListingFix {
  fix: string;
  title: string;
  evidence: string;
  [extra: string]: unknown;
}

/**
 * CloseBundle — the daily-close ritual bundle (close / closeCSV source).
 *
 * FIELD NAMES ARE THE CROSS-SDK CONTRACT. Required keys:
 * headline, kpis { gmv, true_profit, money_at_risk_usd },
 * reorder_sheet[0] { product, reorder_qty, citation },
 * reply_queue[0] { draft, citation }, po_draft.
 */
export interface CloseBundle {
  /** Wall-clock day "YYYY-MM-DD". */
  date: string;
  /** Shop label (verbatim). */
  shop: string;
  /** One-line owner summary, e.g. "Profit $169.09 (61.7%) · ...". */
  headline: string;
  /** Audited KPIs (see KPIs). */
  kpis: KPIs;
  /** 3 owner actions for today. */
  do_today: string[];
  /** Reorder sheet rows (see ReorderLine). */
  reorder_sheet: ReorderLine[];
  /** Dead-stock notes (title + evidence). */
  dead_stock_note: Array<{ title: string; evidence: string }>;
  /** Reply queue drafts (see ReplyItem). */
  reply_queue: ReplyItem[];
  /** Money leaks with dollar amounts. */
  money_leaks: MoneyLeak[];
  /** Listing fixes for tomorrow's sales. */
  listing_fixes: ListingFix[];
  /** Supplier PO email draft ("Subject: Reorder ..."). */
  po_draft: string;
  /** Audit pointer ("every number cites [file:line] ..."). */
  citations: string;
  /** $0 local-first flags. */
  free: boolean;
  offline: boolean;
  [extra: string]: unknown;
}

/**
 * CSV bundle for a close (closeCSV return).
 */
export interface CloseCSVBundle {
  /** close.csv content (KPIs + do_today + reorder + leaks). */
  closeCsv: string;
  /** reorder.csv content. */
  reorderCsv: string;
  /** replies.txt content (reply drafts + PO draft). */
  repliesTxt: string;
  /** po.txt content (PO email draft). */
  poTxt: string;
}

// ---------------------------------------------------------------------------
// Client options + fetch injection (testability)
// ---------------------------------------------------------------------------

/** Minimal fetch signature (global fetch compatible, injectable for tests). */
export type FetchFn = (
  input: string | URL | Request,
  init?: RequestInit,
) => Promise<Response>;

/**
 * Constructor options for OmniOneClient.
 */
export interface ClientOptions {
  /**
   * Base URL of the API (e.g. "http://localhost:5003").
   * Empty string = local stub mode (throws OmniOneError on network
   * methods with a helpful message — use the Python client for true
   * in-process local mode).
   */
  baseUrl?: string;
  /** API key sent as `X-API-Key` header when set. */
  apiKey?: string;
  /** Per-request timeout in ms (default 30_000). */
  timeoutMs?: number;
  /** Max attempts incl. retries (default 3). */
  maxAttempts?: number;
  /** Base backoff ms (default 400). Set 0 in tests for speed. */
  backoffMs?: number;
  /**
   * Custom fetch implementation (defaults to globalThis.fetch).
   * Inject a mock in tests to assert retry + header behaviour.
   */
  fetchFn?: FetchFn;
  /** Extra default headers merged into every request. */
  extraHeaders?: Record<string, string>;
}

/**
 * Per-call overrides (timeout / apiKey / signal chaining).
 */
export interface RequestOptions {
  /** Override timeout for this call only. */
  timeoutMs?: number;
  /** Override apiKey for this call only. */
  apiKey?: string;
  /** External AbortSignal (chained with the timeout controller). */
  signal?: AbortSignal;
}

/**
 * Options for briefingDemo.
 */
export interface BriefingDemoOptions extends RequestOptions {
  /** Demo seed (default 42 = golden KPIs). */
  seed?: number;
}

/**
 * Options for briefingFolder.
 */
export interface BriefingFolderOptions extends RequestOptions {
  /** Seller folder path (server-side path when remote). */
  folder: string;
  seed?: number;
}

/**
 * Options for scenariosRun.
 */
export interface ScenariosRunOptions extends RequestOptions {
  demo?: boolean;
  folder?: string;
  seed?: number;
}

/**
 * Options for operations.
 */
export interface OperationsOptions extends RequestOptions {
  seed?: number;
}

/**
 * Options for close.
 */
export interface CloseOptions extends RequestOptions {
  demo?: boolean;
  folder?: string;
  seed?: number;
  shop?: string;
}

/**
 * Options for analyze.
 */
export interface AnalyzeOptions extends RequestOptions {
  records: Array<Record<string, unknown>>;
}

// ---------------------------------------------------------------------------
// Internal helpers (retry, timeout, headers, CSV)
// ---------------------------------------------------------------------------

/** Sleep helper (backoff). Overridable via backoffMs=0 in tests. */
function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * Compute backoff delay for attempt N (1-based retry index).
 * Exponential: base * 2^(retry-1) + jitter(0..100ms).
 */
export function backoffDelayMs(retryIndex: number, baseMs: number): number {
  const exp = baseMs * 2 ** (retryIndex - 1);
  const jitter = Math.floor(Math.random() * 100);
  return exp + jitter;
}

/**
 * True if the request should be retried (429 / 5xx / network error).
 * Non-retryable 4xx returns false (fail fast with the server message).
 */
export function isRetryableStatus(status: number): boolean {
  return RETRYABLE_STATUSES.has(status);
}

/**
 * Build request headers: JSON content-type + X-API-Key when configured.
 * The `X-API-Key` name is load-bearing (server checks it verbatim).
 */
export function buildHeaders(apiKey?: string, extra?: Record<string, string>): Record<string, string> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (apiKey) {
    headers["X-API-Key"] = apiKey;
  }
  if (extra) {
    for (const [k, v] of Object.entries(extra)) {
      headers[k] = v;
    }
  }
  return headers;
}

/**
 * Parse JSON verbatim (citation-preserving).
 *
 * We deliberately do NOT post-process the payload: citation strings like
 * "inventory.csv:2" pass through exactly as the server sent them. No
 * stripping, no lowercasing, no truncation. This function exists to document
 * that guarantee in one place + give a single hook for future revivers that
 * MUST keep citations intact.
 */
export function parseJsonPreservingCitations<T>(text: string): T {
  // NOTE: JSON.parse already preserves strings verbatim. Do not add a
  // reviver that touches `citation` / `evidence` keys.
  return JSON.parse(text) as T;
}

/**
 * Assert a CloseBundle has the contract shape (headline, kpis, reorder,
 * reply, po_draft). Throws OmniOneError on violation. Used by close() to
 * fail fast on server drift instead of passing phantom data downstream.
 */
export function assertCloseShape(bundle: unknown): asserts bundle is CloseBundle {
  const b = bundle as Record<string, unknown>;
  const missing: string[] = [];
  if (typeof b["headline"] !== "string") missing.push("headline");
  const kpis = b["kpis"] as Record<string, unknown> | undefined;
  if (!kpis || typeof kpis !== "object") {
    missing.push("kpis");
  } else {
    for (const k of ["gmv", "true_profit", "money_at_risk_usd"]) {
      if (!(k in kpis)) missing.push(`kpis.${k}`);
    }
  }
  const reorder = b["reorder_sheet"] as unknown[] | undefined;
  if (!Array.isArray(reorder) || reorder.length === 0) {
    missing.push("reorder_sheet[0]");
  } else {
    const r0 = reorder[0] as Record<string, unknown>;
    for (const k of ["product", "reorder_qty", "citation"]) {
      if (!(k in r0)) missing.push(`reorder_sheet[0].${k}`);
    }
  }
  const replies = b["reply_queue"] as unknown[] | undefined;
  if (!Array.isArray(replies) || replies.length === 0) {
    missing.push("reply_queue[0]");
  } else {
    const q0 = replies[0] as Record<string, unknown>;
    for (const k of ["draft", "citation"]) {
      if (!(k in q0)) missing.push(`reply_queue[0].${k}`);
    }
  }
  if (typeof b["po_draft"] !== "string") missing.push("po_draft");
  if (missing.length > 0) {
    throw new OmniOneError(`close bundle missing contract fields: ${missing.join(", ")}`, {
      status: 0,
      path: "/api/v1/seller/close",
      attempts: 1,
    });
  }
}

/**
 * Render briefing KPIs as CSV text (mirrors seller_export.briefing_to_csv).
 * Deterministic row order; citations verbatim.
 */
export function briefingToCsv(briefing: BriefingBundle): string {
  const k = briefing.kpis as Record<string, unknown>;
  const lines: string[] = [];
  lines.push("metric,value");
  for (const key of [
    "gmv",
    "fees",
    "shipping",
    "net",
    "cogs",
    "true_profit",
    "margin_pct",
    "orders",
    "aov",
    "at_risk",
    "stockout_risk",
  ]) {
    lines.push(`${key},${csvCell(k[key])}`);
  }
  const best = (k["best_seller"] as BestSeller | undefined) ?? { product: "", qty: "" };
  lines.push(`best_seller,${csvCell(`${best.product ?? ""} x${best.qty ?? ""}`)}`);
  lines.push("");
  lines.push("alert_severity,alert_message,evidence");
  for (const a of briefing.alerts ?? []) {
    const ev = (a.evidence ?? [""])[0] ?? "";
    lines.push(`${csvCell(a.severity)}${","}${csvCell(a.message)}${","}${csvCell(ev)}`);
  }
  lines.push("");
  lines.push("action_n,action");
  (briefing.actions ?? []).forEach((act, i) => {
    lines.push(`${i + 1},${csvCell(act)}`);
  });
  lines.push("");
  lines.push("stockout_product,on_hand,sold_7d,days_supply,citation");
  for (const r of briefing.stockout_risk ?? []) {
    // citation passes through verbatim (file:line preserved).
    lines.push(
      [r.product, r.on_hand, r.sold_7d, r.days_supply, r.citation].map(csvCell).join(","),
    );
  }
  return lines.join("\n") + "\n";
}

/** CSV-escape one cell (quotes when needed, "" doubled). */
function csvCell(v: unknown): string {
  if (v === null || v === undefined) return "";
  const s = String(v);
  if (s.includes(",") || s.includes('"') || s.includes("\n")) {
    return `"${s.replace(/"/g, '""')}"`;
  }
  return s;
}

/**
 * Render a CloseBundle as close.csv text (mirrors seller_close.close_to_csv).
 * Citations verbatim.
 */
export function closeToCsv(close: CloseBundle): string {
  const lines: string[] = [];
  lines.push(`DAILY CLOSE,${csvCell(close.date)},${csvCell(close.headline)}`);
  lines.push("");
  lines.push("metric,value");
  for (const [k, v] of Object.entries(close.kpis ?? {})) {
    lines.push(`${csvCell(k)},${csvCell(v as unknown)}`);
  }
  lines.push("");
  lines.push("do_today_n,do_today");
  (close.do_today ?? []).forEach((t, i) => {
    lines.push(`${i + 1},${csvCell(t)}`);
  });
  lines.push("");
  lines.push("product,on_hand,sold_7d,days_left,reorder_qty_14d,supplier,urgency,citation");
  for (const r of close.reorder_sheet ?? []) {
    lines.push(
      [
        r.product,
        r.on_hand,
        r.sold_7d,
        r.days_left,
        r.reorder_qty,
        r.supplier,
        r.urgency,
        r.citation, // verbatim file:line
      ]
        .map(csvCell)
        .join(","),
    );
  }
  lines.push("");
  lines.push("leak,amount_usd,note,evidence");
  for (const lk of close.money_leaks ?? []) {
    lines.push(
      [lk.leak, lk.amount_usd ?? "", String(lk.note ?? "").slice(0, 160), lk.evidence]
        .map(csvCell)
        .join(","),
    );
  }
  return lines.join("\n") + "\n";
}

/**
 * Render reorder sheet as reorder.csv (mirrors seller_close.reorder_to_csv).
 */
export function reorderToCsv(close: CloseBundle): string {
  const lines = [
    "product,on_hand,sold_7d,daily_velocity,days_left,reorder_qty_14d,supplier,urgency,citation",
  ];
  for (const r of close.reorder_sheet ?? []) {
    lines.push(
      [
        r.product,
        r.on_hand,
        r.sold_7d,
        r.daily_velocity,
        r.days_left,
        r.reorder_qty,
        r.supplier,
        r.urgency,
        r.citation, // verbatim
      ]
        .map(csvCell)
        .join(","),
    );
  }
  return lines.join("\n") + "\n";
}

/**
 * Render reply queue + PO draft as replies.txt (mirrors replies_to_txt).
 * Drafts + citations verbatim (copy-paste ready).
 */
export function repliesToTxt(close: CloseBundle): string {
  const risk = close.kpis?.money_at_risk_usd ?? 0;
  const out: string[] = [
    `DAILY CLOSE ${close.date} — REPLY QUEUE ($${Number(risk).toFixed(2)} at risk)`,
    "=".repeat(64),
    "",
  ];
  (close.reply_queue ?? []).forEach((q, i) => {
    out.push(
      `[${i + 1}] ${q.priority} — ${q.channel}: ${q.customer}`,
      `    customer said: ${q.summary}`,
      `    evidence: ${q.citation}`,
      `    COPY-PASTE DRAFT: ${q.draft || "(see scenario action)"}`,
      "",
    );
  });
  out.push("PO DRAFT (send to supplier):", "-".repeat(64), close.po_draft ?? "");
  return out.join("\n");
}

// ---------------------------------------------------------------------------
// OmniOneClient — the main class
// ---------------------------------------------------------------------------

/**
 * Omni-One TypeScript client (fetch-based, node18+ & browser).
 *
 * Methods (stable surface, mirrors Python OmniOneClient):
 *  briefingDemo, briefingFolder, scenariosRun, operations, close,
 *  analyze, health, exportCSV, closeCSV.
 *
 * All network calls retry 3 tries on 429/5xx with backoff, enforce a
 * timeout via AbortController, and send `X-API-Key` when configured.
 * Citation strings in responses pass through untouched.
 */
export class OmniOneClient {
  /** Base URL sans trailing slash (""). */
  readonly baseUrl: string;
  /** API key (sent as X-API-Key). */
  readonly apiKey?: string;
  /** Default timeout ms. */
  readonly timeoutMs: number;
  /** Max attempts (default 3). */
  readonly maxAttempts: number;
  /** Base backoff ms (default 400). */
  readonly backoffMs: number;
  /** Fetch implementation. */
  private readonly fetchFn: FetchFn;
  /** Extra default headers. */
  private readonly extraHeaders: Record<string, string>;

  constructor(options: ClientOptions = {}) {
    this.baseUrl = (options.baseUrl ?? "").replace(/\/+$/, "");
    this.apiKey = options.apiKey;
    this.timeoutMs = options.timeoutMs ?? DEFAULT_TIMEOUT_MS;
    this.maxAttempts = options.maxAttempts ?? MAX_ATTEMPTS;
    this.backoffMs = options.backoffMs ?? BASE_BACKOFF_MS;
    const globalFetch = (globalThis as unknown as { fetch?: FetchFn }).fetch;
    if (!options.fetchFn && !globalFetch) {
      throw new OmniOneError("no fetch implementation: pass fetchFn or use node18+/browser", {
        status: 0,
        path: "",
        attempts: 0,
      });
    }
    // eslint-disable-next-line @typescript-eslint/no-non-null-assertion
    this.fetchFn = options.fetchFn ?? globalFetch!;
    this.extraHeaders = options.extraHeaders ?? {};
  }

  /**
   * Create a client pointing at a local dev server default.
   * (True in-process local mode is a Python-client feature; the TS client
   * always speaks HTTP. This helper just presets localhost:5003.)
   */
  static local(options: Omit<ClientOptions, "baseUrl"> = {}): OmniOneClient {
    return new OmniOneClient({ ...options, baseUrl: "http://localhost:5003" });
  }

  /** True when no baseUrl was configured. */
  get isLocal(): boolean {
    return this.baseUrl === "";
  }

  // -- internals ------------------------------------------------------------

  /**
   * Core request with retry + timeout + X-API-Key.
   * Retries 429/5xx (and network errors) up to maxAttempts with backoff.
   */
  private async request<T>(
    method: "GET" | "POST",
    path: string,
    body?: unknown,
    opts: RequestOptions = {},
  ): Promise<T> {
    if (!this.baseUrl) {
      throw new OmniOneError(
        "no baseUrl configured — TS client needs an HTTP server (try OmniOneClient.local() " +
          "against `omni-one serve`, or use the Python client for in-process local mode)",
        { status: 0, path, attempts: 0 },
      );
    }
    const timeoutMs = opts.timeoutMs ?? this.timeoutMs;
    const apiKey = opts.apiKey ?? this.apiKey;
    const url = `${this.baseUrl}${path}`;
    let lastError: unknown = null;

    for (let attempt = 1; attempt <= this.maxAttempts; attempt++) {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), timeoutMs);
      // Chain an external signal when provided.
      const onExternalAbort = (): void => controller.abort();
      if (opts.signal) {
        if (opts.signal.aborted) controller.abort();
        else opts.signal.addEventListener("abort", onExternalAbort, { once: true });
      }
      try {
        const res = await this.fetchFn(url, {
          method,
          headers: buildHeaders(apiKey, this.extraHeaders),
          body: body === undefined ? undefined : JSON.stringify(body),
          signal: controller.signal,
        });
        clearTimeout(timer);
        if (opts.signal) opts.signal.removeEventListener("abort", onExternalAbort);

        if (res.ok) {
          const text = await res.text();
          if (!text) return {} as T;
          // Verbatim parse — citations preserved (file:line untouched).
          return parseJsonPreservingCitations<T>(text);
        }

        // Retryable statuses: 429 / 5xx (and 408).
        if (isRetryableStatus(res.status) && attempt < this.maxAttempts) {
          lastError =
            res.status === 429
              ? new OmniOneRateLimitError(path, attempt)
              : new OmniOneError(`server error ${res.status} on ${path}`, {
                  status: res.status,
                  path,
                  attempts: attempt,
                });
          await sleep(backoffDelayMs(attempt, this.backoffMs));
          continue;
        }
        // Non-retryable (or retries exhausted): surface server message.
        const errText = await res.text().catch(() => "");
        throw new OmniOneError(
          `omni-one ${method} ${path} failed: ${res.status} ${errText.slice(0, 300)}`,
          { status: res.status, path, attempts: attempt },
        );
      } catch (err) {
        clearTimeout(timer);
        if (opts.signal) opts.signal.removeEventListener("abort", onExternalAbort);
        // Timeout -> typed error (retryable while attempts remain).
        const aborted =
          (controller.signal.aborted && !(opts.signal && opts.signal.aborted)) ||
          (err instanceof Error && err.name === "AbortError");
        if (aborted && !(opts.signal && opts.signal.aborted)) {
          lastError = new OmniOneTimeoutError(path, timeoutMs, attempt);
          if (attempt < this.maxAttempts) {
            await sleep(backoffDelayMs(attempt, this.backoffMs));
            continue;
          }
          throw lastError;
        }
        // Caller-cancelled: do not retry, propagate as-is.
        if (opts.signal && opts.signal.aborted) throw err;
        // OmniOneError with non-retryable status: propagate.
        if (err instanceof OmniOneError && err.status !== 0 && !isRetryableStatus(err.status)) {
          throw err;
        }
        // Network error (status 0): retry while attempts remain.
        if (attempt < this.maxAttempts) {
          lastError = err;
          await sleep(backoffDelayMs(attempt, this.backoffMs));
          continue;
        }
        if (err instanceof OmniOneError) throw err;
        throw new OmniOneError(
          `omni-one ${method} ${path} network error after ${attempt} attempt(s): ${
            err instanceof Error ? err.message : String(err)
          }`,
          { status: 0, path, attempts: attempt },
        );
      }
    }
    // Unreachable in practice; keeps TS exhaustiveness happy.
    throw lastError instanceof Error
      ? lastError
      : new OmniOneError(`request failed: ${path}`, { status: 0, path, attempts: this.maxAttempts });
  }

  /** POST helper (JSON in, JSON out, citations preserved). */
  private post<T>(path: string, payload: unknown, opts?: RequestOptions): Promise<T> {
    return this.request<T>("POST", path, payload, opts);
  }

  /** GET helper (JSON out, citations preserved). */
  private get<T>(path: string, opts?: RequestOptions): Promise<T> {
    return this.request<T>("GET", path, undefined, opts);
  }

  // -- Seller OS ------------------------------------------------------------

  /**
   * Demo briefing (golden KPIs: GMV 274.00 / true_profit 169.09).
   * POST /api/v1/seller/briefing { demo: true, seed }.
   */
  async briefingDemo(options: BriefingDemoOptions = {}): Promise<BriefingBundle> {
    const { seed = 42, ...req } = options;
    return this.post<BriefingBundle>("/api/v1/seller/briefing", { demo: true, seed }, req);
  }

  /**
   * Briefing for a server-side seller folder.
   * POST /api/v1/seller/briefing { folder, seed }.
   */
  async briefingFolder(
    folder: string,
    options: BriefingFolderOptions | RequestOptions = {},
  ): Promise<BriefingBundle> {
    const seed = (options as BriefingFolderOptions).seed ?? 42;
    return this.post<BriefingBundle>("/api/v1/seller/briefing", { folder, seed }, options);
  }

  /**
   * Run the 12 seller scenarios -> ranked Workshop decisions.
   * POST /api/v1/seller/scenarios/run { demo, folder, seed }.
   */
  async scenariosRun(options: ScenariosRunOptions = {}): Promise<ScenariosResult> {
    const { demo = true, folder, seed = 42, ...req } = options;
    return this.post<ScenariosResult>(
      "/api/v1/seller/scenarios/run",
      { demo, folder, seed },
      req,
    );
  }

  /**
   * Full ops loop (briefing KPIs + workshop + governance stats).
   * POST /api/v1/seller/operations { demo: true, seed }.
   */
  async operations(options: OperationsOptions = {}): Promise<OperationsResult> {
    const { seed = 42, ...req } = options;
    return this.post<OperationsResult>("/api/v1/seller/operations", { demo: true, seed }, req);
  }

  /**
   * DAILY CLOSE bundle (profit, reorder+PO, reply drafts, leaks).
   * POST /api/v1/seller/close { demo, folder, seed, shop }.
   * Validates the contract shape (headline, kpis, reorder_sheet,
   * reply_queue, po_draft) before returning.
   */
  async close(options: CloseOptions = {}): Promise<CloseBundle> {
    const { demo = true, folder, seed = 42, shop = "our shop", ...req } = options;
    const bundle = await this.post<CloseBundle>(
      "/api/v1/seller/close",
      { demo, folder, seed, shop },
      req,
    );
    assertCloseShape(bundle);
    return bundle;
  }

  /**
   * Generic analyze call. POST /api/v1/analyze { records }.
   */
  async analyze(
    records: Array<Record<string, unknown>>,
    options: RequestOptions = {},
  ): Promise<AnalyzeResult> {
    return this.post<AnalyzeResult>("/api/v1/analyze", { records }, options);
  }

  /**
   * Health check. GET /health.
   */
  async health(options: RequestOptions = {}): Promise<HealthResult> {
    return this.get<HealthResult>("/health", options);
  }

  /**
   * Briefing -> CSV text (for Sheets/accounting). Fetches the briefing then
   * renders locally (deterministic, citations verbatim).
   */
  async exportCSV(
    options: CloseOptions = {},
  ): Promise<string> {
    const { demo = true, folder, seed = 42, ...req } = options;
    const briefing =
      demo || !folder
        ? await this.briefingDemo({ seed, ...req })
        : await this.briefingFolder(folder, { seed, ...req });
    return briefingToCsv(briefing);
  }

  /**
   * Daily close -> CSV bundle (close.csv + reorder.csv + replies.txt + po).
   * Fetches close() then renders all four artefacts locally.
   */
  async closeCSV(options: CloseOptions = {}): Promise<CloseCSVBundle> {
    const bundle = await this.close(options);
    return {
      closeCsv: closeToCsv(bundle),
      reorderCsv: reorderToCsv(bundle),
      repliesTxt: repliesToTxt(bundle),
      poTxt: bundle.po_draft ?? "",
    };
  }
}

// ---------------------------------------------------------------------------
// Default export (CJS-friendly: `const { OmniOneClient } = require(...)`
// works alongside `import { OmniOneClient } from ...`).
// ---------------------------------------------------------------------------

export default OmniOneClient;

// ---------------------------------------------------------------------------
// Re-exports from close.ts live in that module to avoid cycles; the key
// close helpers are ALSO defined here (closeToCsv/reorderToCsv/repliesToTxt)
// so single-file consumers (`import ... from "./index.js"`) need no second
// import. close.ts re-exports them for the "./close" subpath.
// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
// Appendix: endpoint map (for server implementers + Go SDK parity)
// ---------------------------------------------------------------------------
/**
 * ENDPOINT MAP
 *  POST /api/v1/seller/briefing       { demo, folder?, seed }  -> BriefingBundle
 *  POST /api/v1/seller/scenarios/run  { demo, folder?, seed }  -> ScenariosResult
 *  POST /api/v1/seller/operations     { demo, seed }           -> OperationsResult
 *  POST /api/v1/seller/close          { demo, folder?, seed, shop } -> CloseBundle
 *  POST /api/v1/analyze               { records }              -> AnalyzeResult
 *  GET  /health                                                -> HealthResult
 *
 * AUTH: X-API-Key header when apiKey configured (server enforces iff set).
 * RETRY: 3 tries on 429/5xx/408 + network errors; backoff 400/800ms+jitter.
 * TIMEOUT: 30s default per attempt (AbortController).
 * CITATIONS: every response field named `citation` / `evidence` passes
 * through verbatim (file:line). Client never rewrites them; CSV renderers
 * copy them cell-for-cell.
 */
export const ENDPOINTS = {
  briefing: "/api/v1/seller/briefing",
  scenariosRun: "/api/v1/seller/scenarios/run",
  operations: "/api/v1/seller/operations",
  close: "/api/v1/seller/close",
  analyze: "/api/v1/analyze",
  health: "/health",
} as const;

/** Endpoint path union type. */
export type EndpointPath = (typeof ENDPOINTS)[keyof typeof ENDPOINTS];
