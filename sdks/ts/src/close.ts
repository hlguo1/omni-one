/**
 * Omni-One TS SDK — close submodule (`@omni-one/sdk-ts/close`).
 * =====================================================================
 * Re-exports the close helpers + types for consumers who only need the
 * daily-close ritual (smaller import surface, same citation guarantees).
 *
 * ```ts
 * import { closeToCsv, repliesToTxt, assertCloseShape } from "@omni-one/sdk-ts/close";
 * import type { CloseBundle, ReorderLine, ReplyItem, KPIs } from "@omni-one/sdk-ts/close";
 * ```
 *
 * CITATION RULE (load-bearing): every helper copies `citation` / `evidence`
 * / `draft` / `po_draft` strings VERBATIM (file:line preserved). Never
 * strip, lowercase, truncate, or re-map them. The smoke test
 * (tests/run.mjs) asserts citations still match /inventory\.csv:/ after
 * each transform.
 */

export type {
  CloseBundle,
  CloseCSVBundle,
  KPIs,
  BestSeller,
  ReorderLine,
  ReplyItem,
  MoneyLeak,
  ListingFix,
  BriefingBundle,
  ScenarioDecision,
  ScenariosResult,
} from "./index.js";

export {
  OmniOneClient,
  OmniOneError,
  OmniOneTimeoutError,
  OmniOneRateLimitError,
  assertCloseShape,
  briefingToCsv,
  closeToCsv,
  reorderToCsv,
  repliesToTxt,
  parseJsonPreservingCitations,
  isRetryableStatus,
  backoffDelayMs,
  buildHeaders,
  ENDPOINTS,
  SDK_VERSION,
  DEFAULT_TIMEOUT_MS,
  MAX_ATTEMPTS,
  BASE_BACKOFF_MS,
  RETRYABLE_STATUSES,
} from "./index.js";

import type { CloseBundle } from "./index.js";

/**
 * One-line owner summary for a close (headline passthrough).
 * Returns close.headline verbatim — no rewriting.
 */
export function closeHeadline(close: CloseBundle): string {
  return close.headline;
}

/**
 * True-profit accessor (close.kpis.true_profit passthrough).
 */
export function closeTrueProfit(close: CloseBundle): number {
  return close.kpis.true_profit;
}

/**
 * Money-at-risk accessor (close.kpis.money_at_risk_usd passthrough).
 */
export function closeMoneyAtRisk(close: CloseBundle): number {
  return close.kpis.money_at_risk_usd;
}

/**
 * SKUs that must be reordered TODAY (urgency === "ORDER TODAY").
 * Rows pass through by reference (citations intact).
 */
export function closeReordersToday(close: CloseBundle): CloseBundle["reorder_sheet"] {
  return (close.reorder_sheet ?? []).filter((r) => r.urgency === "ORDER TODAY");
}

/**
 * P0 replies (priority === "P0-reply-in-2h"). Drafts + citations intact.
 */
export function closeP0Replies(close: CloseBundle): CloseBundle["reply_queue"] {
  return (close.reply_queue ?? []).filter((q) => q.priority === "P0-reply-in-2h");
}

export default {
  closeHeadline,
  closeTrueProfit,
  closeMoneyAtRisk,
  closeReordersToday,
  closeP0Replies,
};
