// Package omnionego is the Omni-One Go SDK — local-first seller OS client.
//
// Fetch-based via net/http, context timeouts, retry with backoff, X-API-Key
// auth, typed structs, citation-preserving JSON. $0, offline-friendly.
//
// Quickstart:
//
//	c := omnionego.NewClient("http://localhost:5003", "")
//	h, err := c.Health(ctx)
//	b, err := c.BriefingDemo(ctx, 42)   // GMV 274.00 / profit 169.09
//	close, err := c.Close(ctx, CloseOptions{Demo: true})
//	fmt.Println(close.Headline)                    // "Profit $169.09 ..."
//	fmt.Println(close.KPIs.TrueProfit)             // 169.09
//	fmt.Println(close.KPIs.MoneyAtRiskUSD)         // > 0
//	fmt.Println(close.ReorderSheet[0].Citation)    // "inventory.csv:2" verbatim
//
// DESIGN RULES (mirror src/omni_one/client.py + sdks/ts/src/index.ts):
//   - Retry with backoff: 3 tries total on 429 / 408 / 5xx + network errors.
//     Backoff 400ms -> 800ms + jitter. Other 4xx fail fast.
//   - Timeout: context.WithTimeout per attempt (default 30s). Pass your own
//     ctx to chain cancellation; DeadlineExceeded is typed.
//   - Auth: API key sent as `X-API-Key` header when configured.
//   - file:line passthrough: citation strings (e.g. "inventory.csv:2") are
//     NEVER stripped, lowercased, truncated, or re-mapped. encoding/json
//     preserves strings verbatim; helpers copy them cell-for-cell.
//   - Typed structs: CloseBundle, KPIs, ReorderLine, ReplyItem (+ friends).
//     JSON tags are the cross-SDK contract — tests/unit/test_sdk_contract.py
//     greps for json:"headline", json:"true_profit", etc. Do not rename tags
//     without updating Python + TS SDKs together.
//
// CITATION CONTRACT (both SDKs must satisfy the python contract test):
//
//	CloseBundle fields: headline, kpis { gmv, true_profit, money_at_risk_usd },
//	reorder_sheet[0] { product, reorder_qty, citation },
//	reply_queue[0] { draft, citation }, po_draft.
//
// Thread-safety: Client is safe for concurrent use (no mutable per-call
// state; http.Client is shared).
package omnionego

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"math/rand"
	"net/http"
	"strings"
	"time"
)

// ---------------------------------------------------------------------------
// Version + defaults
// ---------------------------------------------------------------------------

// SDKVersion mirrors the module release line (keep in sync with ts SDK).
const SDKVersion = "1.1.0"

// DefaultTimeout is the per-attempt timeout (30s, mirrors Python SDK).
const DefaultTimeout = 30 * time.Second

// MaxAttempts is the total tries per call (initial + 2 retries = 3 tries).
const MaxAttempts = 3

// BaseBackoff is the backoff base (attempt 1 -> ~400ms, attempt 2 -> ~800ms).
const BaseBackoff = 400 * time.Millisecond

// APIKeyHeader is the auth header name (load-bearing: server checks verbatim).
const APIKeyHeader = "X-API-Key"

// Endpoints (mirror the FastAPI app + TS SDK ENDPOINTS map).
const (
	EndpointBriefing     = "/api/v1/seller/briefing"
	EndpointScenariosRun = "/api/v1/seller/scenarios/run"
	EndpointOperations   = "/api/v1/seller/operations"
	EndpointClose        = "/api/v1/seller/close"
	EndpointAnalyze      = "/api/v1/analyze"
	EndpointHealth       = "/health"
)

// retryableStatus reports whether an HTTP status is worth retrying.
func retryableStatus(code int) bool {
	switch code {
	case http.StatusRequestTimeout, // 408
		http.StatusTooManyRequests,     // 429
		http.StatusInternalServerError, // 500
		http.StatusBadGateway,          // 502
		http.StatusServiceUnavailable,  // 503
		http.StatusGatewayTimeout:      // 504
		return true
	default:
		return false
	}
}

// backoffFor computes the backoff before retry number retry (1-based).
// Exponential: base * 2^(retry-1) + jitter(0..100ms). Deterministic shape,
// random jitter only (never affects correctness).
func backoffFor(retry int, base time.Duration) time.Duration {
	exp := base * time.Duration(1<<(retry-1))
	jitter := time.Duration(rand.Int63n(int64(100 * time.Millisecond)))
	return exp + jitter
}

// ---------------------------------------------------------------------------
// Errors
// ---------------------------------------------------------------------------

// Error is the base SDK error: status + path + attempts for debuggability.
type Error struct {
	// Status is the HTTP status (0 = network/timeout, no response).
	Status int
	// Path is the API path that failed (e.g. "/api/v1/seller/close").
	Path string
	// Attempts counts tries made (1..MaxAttempts).
	Attempts int
	// Msg is the human message (includes server body excerpt when known).
	Msg string
}

// Error implements error.
func (e *Error) Error() string {
	if e.Status != 0 {
		return fmt.Sprintf("omnionego: %s %s failed: status %d after %d attempt(s): %s",
			"request", e.Path, e.Status, e.Attempts, e.Msg)
	}
	return fmt.Sprintf("omnionego: request %s failed after %d attempt(s): %s",
		e.Path, e.Attempts, e.Msg)
}

// TimeoutError is returned when the per-attempt context deadline fires.
type TimeoutError struct {
	// Path is the API path that timed out.
	Path string
	// Timeout is the budget that fired.
	Timeout time.Duration
	// Attempts counts tries made.
	Attempts int
}

// Error implements error.
func (e *TimeoutError) Error() string {
	return fmt.Sprintf("omnionego: request %s timed out after %s (%d attempt(s))",
		e.Path, e.Timeout, e.Attempts)
}

// RateLimitError is returned when 429 persists through all retries.
type RateLimitError struct {
	// Path is the API path that stayed limited.
	Path string
	// Attempts counts tries made.
	Attempts int
}

// Error implements error.
func (e *RateLimitError) Error() string {
	return fmt.Sprintf("omnionego: rate limited (429) on %s after %d attempt(s)",
		e.Path, e.Attempts)
}

// ---------------------------------------------------------------------------
// Typed structs — the contract surface.
//
// JSON TAGS ARE LOAD-BEARING: tests/unit/test_sdk_contract.py greps this
// file for json:"headline", json:"gmv", json:"true_profit",
// json:"money_at_risk_usd", json:"reorder_sheet", json:"product",
// json:"reorder_qty", json:"citation", json:"reply_queue", json:"draft",
// json:"po_draft". Keep them exact.
// ---------------------------------------------------------------------------

// BestSeller summarises the top product.
type BestSeller struct {
	// Product is the display name, verbatim (e.g. "Tote Bag Handmade").
	Product string `json:"product"`
	// Qty is units sold.
	Qty int `json:"qty"`
}

// KPIs holds audited seller KPIs.
//
// Golden demo values (seed 42): GMV 274.00, TrueProfit 169.09,
// MoneyAtRiskUSD > 0, Orders 8.
type KPIs struct {
	// GMV is gross merchandise value (e.g. 274.00). json:"gmv".
	GMV float64 `json:"gmv"`
	// Fees are marketplace fees. json:"fees".
	Fees float64 `json:"fees"`
	// Shipping cost. json:"shipping".
	Shipping float64 `json:"shipping"`
	// Net = GMV - Fees - Shipping. json:"net".
	Net float64 `json:"net"`
	// COGS from supplier invoices. json:"cogs".
	COGS float64 `json:"cogs"`
	// TrueProfit is GOLDEN: Net - COGS (e.g. 169.09). json:"true_profit".
	TrueProfit float64 `json:"true_profit"`
	// MarginPct = TrueProfit/GMV*100 (e.g. 61.7). json:"margin_pct".
	MarginPct float64 `json:"margin_pct"`
	// Orders count (golden: 8). json:"orders".
	Orders int `json:"orders"`
	// AOV is average order value. json:"aov".
	AOV float64 `json:"aov"`
	// BestSeller top product. json:"best_seller".
	BestSeller BestSeller `json:"best_seller"`
	// MoneyAtRiskUSD = len(reply_queue)*AOV. json:"money_at_risk_usd".
	MoneyAtRiskUSD float64 `json:"money_at_risk_usd"`
}

// AlertItem is one briefing alert with evidence file:line.
type AlertItem struct {
	// Severity e.g. "high".
	Severity string `json:"severity"`
	// Message human text.
	Message string `json:"message"`
	// Evidence file:line list (verbatim, never stripped).
	Evidence []string `json:"evidence,omitempty"`
}

// StockoutRow is one briefing stockout-risk row.
type StockoutRow struct {
	// Product display name.
	Product string `json:"product"`
	// OnHand units.
	OnHand int `json:"on_hand"`
	// Sold7d units sold last 7 days.
	Sold7d int `json:"sold_7d"`
	// DaysSupply cover left.
	DaysSupply float64 `json:"days_supply"`
	// Citation file:line (verbatim). json:"citation".
	Citation string `json:"citation"`
}

// AtRiskPreview is one at-risk DM/review snippet + citation.
type AtRiskPreview struct {
	// Text snippet.
	Text string `json:"text"`
	// Citation file:line (verbatim). json:"citation".
	Citation string `json:"citation"`
	// Source e.g. "dm".
	Source string `json:"source"`
}

// BriefingBundle is the seller briefing (BriefingDemo / BriefingFolder).
type BriefingBundle struct {
	// KPIs audited numbers.
	KPIs KPIs `json:"kpis"`
	// Alerts list.
	Alerts []AlertItem `json:"alerts"`
	// Actions owner to-dos.
	Actions []string `json:"actions"`
	// StockoutRisk rows.
	StockoutRisk []StockoutRow `json:"stockout_risk"`
	// AtRiskPreview message snippets.
	AtRiskPreview []AtRiskPreview `json:"at_risk_preview,omitempty"`
}

// ScenarioDecision is one ranked scenario decision.
type ScenarioDecision struct {
	// Scenario code e.g. "STOCKOUT_RISK".
	Scenario string `json:"scenario,omitempty"`
	// ScenarioID alias used by some endpoints.
	ScenarioID string `json:"scenario_id,omitempty"`
	// Severity e.g. "P0".
	Severity string `json:"severity,omitempty"`
	// Title human summary.
	Title string `json:"title,omitempty"`
	// Evidence file:line list (verbatim).
	Evidence []string `json:"evidence,omitempty"`
	// Action workshop action.
	Action string `json:"action,omitempty"`
}

// ScenariosResult is the scenarios run output.
type ScenariosResult struct {
	// Total decision count.
	Total int `json:"total"`
	// ByScenario counts per scenario.
	ByScenario map[string]int `json:"by_scenario,omitempty"`
	// Decisions ranked list.
	Decisions []ScenarioDecision `json:"decisions"`
}

// OperationsResult is the full ops loop output.
type OperationsResult struct {
	// BriefingKPIs snapshot. json:"briefing_kpis".
	BriefingKPIs KPIs `json:"briefing_kpis"`
	// Workshop stats. json:"workshop".
	Workshop map[string]any `json:"workshop"`
	// Governance stats. json:"governance".
	Governance map[string]any `json:"governance"`
}

// AnalyzeResult is the generic analyze output.
type AnalyzeResult struct {
	// RecordsProcessed echo. json:"records_processed".
	RecordsProcessed int `json:"records_processed"`
	// Metrics pipeline summary. json:"metrics".
	Metrics map[string]any `json:"metrics"`
}

// HealthResult is the health check output.
type HealthResult struct {
	// Status e.g. "alive". json:"status".
	Status string `json:"status"`
	// Mode e.g. "local". json:"mode,omitempty".
	Mode string `json:"mode,omitempty"`
	// Service e.g. "omni-one". json:"service,omitempty".
	Service string `json:"service,omitempty"`
}

// ReorderLine is one row of the reorder sheet.
//
// CITATION RULE: Citation (file:line, e.g. "inventory.csv:2") passes through
// verbatim. Never strip / rewrite / truncate it.
type ReorderLine struct {
	// Product display name, verbatim. json:"product".
	Product string `json:"product"`
	// OnHand units. json:"on_hand".
	OnHand int `json:"on_hand"`
	// Sold7d units sold last 7d. json:"sold_7d".
	Sold7d int `json:"sold_7d"`
	// DailyVelocity = Sold7d/7. json:"daily_velocity".
	DailyVelocity float64 `json:"daily_velocity"`
	// DaysLeft cover remaining. json:"days_left".
	DaysLeft float64 `json:"days_left"`
	// ReorderQty = ceil(velocity*14 - onHand), floored 0. json:"reorder_qty".
	ReorderQty int `json:"reorder_qty"`
	// CoverDays window (14). json:"cover_days".
	CoverDays int `json:"cover_days"`
	// Supplier from inventory.csv. json:"supplier".
	Supplier string `json:"supplier"`
	// Urgency ORDER TODAY | this week | watch. json:"urgency".
	Urgency string `json:"urgency"`
	// Citation file:line (NEVER stripped). json:"citation".
	Citation string `json:"citation"`
}

// ReplyItem is one copy-paste customer reply draft.
//
// CITATION RULE: Citation + Draft pass through verbatim.
type ReplyItem struct {
	// Channel dm | review | scenario. json:"channel".
	Channel string `json:"channel"`
	// Customer first name / handle. json:"customer".
	Customer string `json:"customer"`
	// Summary 120-char snippet. json:"summary".
	Summary string `json:"summary"`
	// Draft copy-paste reply (>40 chars). json:"draft".
	Draft string `json:"draft"`
	// Citation file:line answered. json:"citation".
	Citation string `json:"citation"`
	// Priority P0-reply-in-2h | P1-today. json:"priority".
	Priority string `json:"priority"`
}

// MoneyLeak is one leak with dollar amount + evidence.
type MoneyLeak struct {
	// Leak code e.g. "fee_creep". json:"leak".
	Leak string `json:"leak"`
	// AmountUSD dollars (nil-able -> pointer). json:"amount_usd".
	AmountUSD *float64 `json:"amount_usd"`
	// Note human explanation. json:"note".
	Note string `json:"note"`
	// Evidence file:line. json:"evidence".
	Evidence string `json:"evidence"`
}

// ListingFix is one listing suggestion.
type ListingFix struct {
	// Fix code. json:"fix".
	Fix string `json:"fix"`
	// Title summary. json:"title".
	Title string `json:"title"`
	// Evidence file:line. json:"evidence".
	Evidence string `json:"evidence"`
}

// DeadStockNote is one dead-stock line.
type DeadStockNote struct {
	// Title summary. json:"title".
	Title string `json:"title"`
	// Evidence file:line. json:"evidence".
	Evidence string `json:"evidence"`
}

// CloseBundle is the daily-close ritual bundle.
//
// CONTRACT FIELDS (all json tags load-bearing):
// headline, kpis { gmv, true_profit, money_at_risk_usd },
// reorder_sheet[0] { product, reorder_qty, citation },
// reply_queue[0] { draft, citation }, po_draft.
type CloseBundle struct {
	// Date wall-clock day "YYYY-MM-DD". json:"date".
	Date string `json:"date"`
	// Shop label verbatim. json:"shop".
	Shop string `json:"shop"`
	// Headline one-line owner summary. json:"headline".
	Headline string `json:"headline"`
	// KPIs audited numbers. json:"kpis".
	KPIs KPIs `json:"kpis"`
	// DoToday 3 owner actions. json:"do_today".
	DoToday []string `json:"do_today"`
	// ReorderSheet rows. json:"reorder_sheet".
	ReorderSheet []ReorderLine `json:"reorder_sheet"`
	// DeadStockNote list. json:"dead_stock_note".
	DeadStockNote []DeadStockNote `json:"dead_stock_note"`
	// ReplyQueue drafts. json:"reply_queue".
	ReplyQueue []ReplyItem `json:"reply_queue"`
	// MoneyLeaks with dollars. json:"money_leaks".
	MoneyLeaks []MoneyLeak `json:"money_leaks"`
	// ListingFixes suggestions. json:"listing_fixes".
	ListingFixes []ListingFix `json:"listing_fixes"`
	// PODraft supplier email ("Subject: Reorder ..."). json:"po_draft".
	PODraft string `json:"po_draft"`
	// Citations audit pointer. json:"citations".
	Citations string `json:"citations"`
	// Free $0 flag. json:"free".
	Free bool `json:"free"`
	// Offline flag. json:"offline".
	Offline bool `json:"offline"`
}

// CloseCSVBundle holds rendered close artefacts (CloseCSV return).
type CloseCSVBundle struct {
	// CloseCSV is close.csv content.
	CloseCSV string
	// ReorderCSV is reorder.csv content.
	ReorderCSV string
	// RepliesTxt is replies.txt content.
	RepliesTxt string
	// POTxt is po.txt content.
	POTxt string
}

// ---------------------------------------------------------------------------
// Options
// ---------------------------------------------------------------------------

// Options configures a Client.
type Options struct {
	// BaseURL of the API (e.g. "http://localhost:5003"). Empty = unset.
	BaseURL string
	// APIKey sent as X-API-Key when non-empty.
	APIKey string
	// Timeout per attempt (default DefaultTimeout).
	Timeout time.Duration
	// MaxAttempts incl. retries (default MaxAttempts=3).
	MaxAttempts int
	// Backoff base (default BaseBackoff). Zero = no sleep (tests).
	Backoff time.Duration
	// HTTPClient override (default &http.Client{}). Inject fakes in tests.
	HTTPClient *http.Client
	// ExtraHeaders merged into every request.
	ExtraHeaders map[string]string
}

// BriefingDemoOptions for BriefingDemo.
type BriefingDemoOptions struct {
	// Seed demo seed (default 42 = golden KPIs).
	Seed int
}

// BriefingFolderOptions for BriefingFolder.
type BriefingFolderOptions struct {
	// Folder server-side seller path.
	Folder string
	// Seed (default 42).
	Seed int
}

// ScenariosRunOptions for ScenariosRun.
type ScenariosRunOptions struct {
	// Demo use demo data (default true).
	Demo bool
	// Folder server-side path when Demo=false.
	Folder string
	// Seed (default 42).
	Seed int
}

// OperationsOptions for Operations.
type OperationsOptions struct {
	// Seed (default 42).
	Seed int
}

// CloseOptions for Close.
type CloseOptions struct {
	// Demo use demo data (default true).
	Demo bool
	// Folder server-side path when Demo=false.
	Folder string
	// Seed (default 42).
	Seed int
	// Shop label (default "our shop").
	Shop string
}

// ---------------------------------------------------------------------------
// Client
// ---------------------------------------------------------------------------

// Client is the Omni-One Go client (safe for concurrent use).
//
// Methods (stable surface, mirrors Python + TS SDKs):
// BriefingDemo, BriefingFolder, ScenariosRun, Operations, Close,
// Analyze, Health, ExportCSV, CloseCSV.
type Client struct {
	baseURL      string
	apiKey       string
	timeout      time.Duration
	maxAttempts  int
	backoff      time.Duration
	http         *http.Client
	extraHeaders map[string]string
}

// NewClient builds a Client for baseURL with apiKey ("").
//
//	baseURL e.g. "http://localhost:5003" (trailing slash trimmed).
//	Pass Options via NewClientWithOptions for timeouts/headers/fakes.
func NewClient(baseURL, apiKey string) *Client {
	return NewClientWithOptions(Options{BaseURL: baseURL, APIKey: apiKey})
}

// NewClientWithOptions builds a Client from Options (zero value = defaults).
func NewClientWithOptions(o Options) *Client {
	base := strings.TrimRight(o.BaseURL, "/")
	timeout := o.Timeout
	if timeout == 0 {
		timeout = DefaultTimeout
	}
	attempts := o.MaxAttempts
	if attempts == 0 {
		attempts = MaxAttempts
	}
	backoff := o.Backoff
	if backoff == 0 && !oNoBackoff(o) {
		backoff = BaseBackoff
	}
	hc := o.HTTPClient
	if hc == nil {
		hc = &http.Client{}
	}
	return &Client{
		baseURL:      base,
		apiKey:       o.APIKey,
		timeout:      timeout,
		maxAttempts:  attempts,
		backoff:      backoff,
		http:         hc,
		extraHeaders: o.ExtraHeaders,
	}
}

// oNoBackoff reports whether the caller explicitly wants zero backoff.
// (Options{Backoff: 0} is ambiguous with unset; we treat explicit negative
// as the zero-backoff signal and normalise it.)
func oNoBackoff(o Options) bool {
	return o.Backoff < 0
}

// WithBackoffZero returns a copy with no retry sleep (tests).
func (c *Client) WithBackoffZero() *Client {
	cp := *c
	cp.backoff = 0
	return &cp
}

// BaseURL returns the configured base URL.
func (c *Client) BaseURL() string { return c.baseURL }

// IsLocal reports whether no base URL was configured.
func (c *Client) IsLocal() bool { return c.baseURL == "" }

// LocalClient returns a client preset to the dev server default.
func LocalClient(apiKey string) *Client {
	return NewClient("http://localhost:5003", apiKey)
}

// ---------------------------------------------------------------------------
// Internals: do (retry + timeout + X-API-Key, citation-preserving JSON)
// ---------------------------------------------------------------------------

// headers builds per-request headers: JSON content-type + X-API-Key.
func (c *Client) headers() http.Header {
	h := http.Header{}
	h.Set("Content-Type", "application/json")
	if c.apiKey != "" {
		h.Set(APIKeyHeader, c.apiKey)
	}
	for k, v := range c.extraHeaders {
		h.Set(k, v)
	}
	return h
}

// do performs method+path with optional JSON body, decoding JSON into out.
// Retries 429/408/5xx + network errors up to maxAttempts with backoff.
// Citations pass through verbatim: encoding/json preserves strings as-is;
// we never post-process citation/evidence fields.
func (c *Client) do(ctx context.Context, method, path string, body any, out any) error {
	if c.baseURL == "" {
		return &Error{Status: 0, Path: path, Attempts: 0,
			Msg: "no baseURL configured — Go client needs an HTTP server " +
				"(serve `omni-one serve` or use LocalClient); " +
				"in-process local mode is a Python-client feature"}
	}
	url := c.baseURL + path
	var lastErr error
	for attempt := 1; attempt <= c.maxAttempts; attempt++ {
		// Per-attempt timeout chained onto the caller's ctx.
		attemptCtx, cancel := context.WithTimeout(ctx, c.timeout)
		err := c.doOnce(attemptCtx, method, url, path, attempt, body, out)
		cancel()
		if err == nil {
			return nil
		}
		lastErr = err
		// Decide retryability: typed errors carry the verdict.
		var e *Error
		var t *TimeoutError
		var r *RateLimitError
		switch {
		case asRateLimit(err, &r):
			if attempt < c.maxAttempts {
				sleepBackoff(attempt, c.backoff)
				continue
			}
			return err
		case asTimeout(err, &t):
			// Caller cancellation (parent ctx done) is NOT retried.
			if ctx.Err() != nil {
				return err
			}
			if attempt < c.maxAttempts {
				sleepBackoff(attempt, c.backoff)
				continue
			}
			return err
		case asSDKError(err, &e):
			if e.Status != 0 && !retryableStatus(e.Status) {
				return err // fail fast on non-retryable 4xx
			}
			if attempt < c.maxAttempts {
				sleepBackoff(attempt, c.backoff)
				continue
			}
			return err
		default:
			// Network error (no status): retry while attempts remain.
			if attempt < c.maxAttempts {
				sleepBackoff(attempt, c.backoff)
				continue
			}
			return err
		}
	}
	if lastErr != nil {
		return lastErr
	}
	return &Error{Status: 0, Path: path, Attempts: c.maxAttempts, Msg: "request failed"}
}

// doOnce performs a single attempt.
func (c *Client) doOnce(ctx context.Context, method, url, path string, attempt int, body any, out any) error {
	var rdr io.Reader
	if body != nil {
		buf, err := json.Marshal(body)
		if err != nil {
			return &Error{Status: 0, Path: path, Attempts: attempt, Msg: "marshal: " + err.Error()}
		}
		rdr = bytes.NewReader(buf)
	}
	req, err := http.NewRequestWithContext(ctx, method, url, rdr)
	if err != nil {
		return &Error{Status: 0, Path: path, Attempts: attempt, Msg: "new request: " + err.Error()}
	}
	for k, vv := range c.headers() {
		for _, v := range vv {
			req.Header.Set(k, v)
		}
	}
	resp, err := c.http.Do(req)
	if err != nil {
		// Context deadline on OUR attempt ctx -> typed timeout (unless parent died).
		if ctx.Err() == context.DeadlineExceeded {
			return &TimeoutError{Path: path, Timeout: c.timeout, Attempts: attempt}
		}
		return &Error{Status: 0, Path: path, Attempts: attempt, Msg: "network: " + err.Error()}
	}
	defer resp.Body.Close()
	raw, err := io.ReadAll(io.LimitReader(resp.Body, 32<<20))
	if err != nil {
		return &Error{Status: resp.StatusCode, Path: path, Attempts: attempt, Msg: "read: " + err.Error()}
	}
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		msg := strings.TrimSpace(string(raw))
		if len(msg) > 300 {
			msg = msg[:300]
		}
		if resp.StatusCode == http.StatusTooManyRequests {
			return &RateLimitError{Path: path, Attempts: attempt}
		}
		return &Error{Status: resp.StatusCode, Path: path, Attempts: attempt, Msg: msg}
	}
	if out == nil || len(bytes.TrimSpace(raw)) == 0 {
		return nil
	}
	// Verbatim decode — citation strings preserved (file:line untouched).
	dec := json.NewDecoder(bytes.NewReader(raw))
	dec.UseNumber()
	if err := dec.Decode(out); err != nil {
		return &Error{Status: resp.StatusCode, Path: path, Attempts: attempt, Msg: "decode: " + err.Error()}
	}
	return nil
}

// sleepBackoff sleeps retry^ backoff (skipped when base <= 0, e.g. tests).
func sleepBackoff(retry int, base time.Duration) {
	if base <= 0 {
		return
	}
	time.Sleep(backoffFor(retry, base))
}

// asSDKError unwraps *Error.
func asSDKError(err error, target **Error) bool {
	for err != nil {
		if e, ok := err.(*Error); ok {
			*target = e
			return true
		}
		u, ok := err.(interface{ Unwrap() error })
		if !ok {
			return false
		}
		err = u.Unwrap()
	}
	return false
}

// asTimeout unwraps *TimeoutError.
func asTimeout(err error, target **TimeoutError) bool {
	for err != nil {
		if e, ok := err.(*TimeoutError); ok {
			*target = e
			return true
		}
		u, ok := err.(interface{ Unwrap() error })
		if !ok {
			return false
		}
		err = u.Unwrap()
	}
	return false
}

// asRateLimit unwraps *RateLimitError.
func asRateLimit(err error, target **RateLimitError) bool {
	for err != nil {
		if e, ok := err.(*RateLimitError); ok {
			*target = e
			return true
		}
		u, ok := err.(interface{ Unwrap() error })
		if !ok {
			return false
		}
		err = u.Unwrap()
	}
	return false
}

// ---------------------------------------------------------------------------
// Methods — stable surface (BriefingDemo, BriefingFolder, ScenariosRun,
// Operations, Close, Analyze, Health, ExportCSV, CloseCSV)
// ---------------------------------------------------------------------------

// BriefingDemo fetches the demo briefing (golden KPIs, seed 42 default).
// POST /api/v1/seller/briefing { demo: true, seed }.
func (c *Client) BriefingDemo(ctx context.Context, seed int) (*BriefingBundle, error) {
	if seed == 0 {
		seed = 42
	}
	var out BriefingBundle
	err := c.do(ctx, http.MethodPost, EndpointBriefing,
		map[string]any{"demo": true, "seed": seed}, &out)
	if err != nil {
		return nil, err
	}
	return &out, nil
}

// BriefingFolder fetches a briefing for a server-side seller folder.
// POST /api/v1/seller/briefing { folder, seed }.
func (c *Client) BriefingFolder(ctx context.Context, o BriefingFolderOptions) (*BriefingBundle, error) {
	seed := o.Seed
	if seed == 0 {
		seed = 42
	}
	var out BriefingBundle
	err := c.do(ctx, http.MethodPost, EndpointBriefing,
		map[string]any{"folder": o.Folder, "seed": seed}, &out)
	if err != nil {
		return nil, err
	}
	return &out, nil
}

// ScenariosRun runs the 12 seller scenarios -> ranked decisions.
// POST /api/v1/seller/scenarios/run { demo, folder, seed }.
func (c *Client) ScenariosRun(ctx context.Context, o ScenariosRunOptions) (*ScenariosResult, error) {
	seed := o.Seed
	if seed == 0 {
		seed = 42
	}
	demo := o.Demo
	if o.Folder == "" {
		// Default to demo when no folder given (mirrors Python SDK).
		demo = true
	} else if !o.Demo {
		// Folder set without explicit demo flag -> folder mode.
		demo = false
	}
	payload := map[string]any{"demo": demo, "seed": seed}
	if o.Folder != "" {
		payload["folder"] = o.Folder
		payload["demo"] = demo
	}
	var out ScenariosResult
	if err := c.do(ctx, http.MethodPost, EndpointScenariosRun, payload, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

// Operations fetches the full ops loop (briefing KPIs + workshop + audit).
// POST /api/v1/seller/operations { demo: true, seed }.
func (c *Client) Operations(ctx context.Context, seed int) (*OperationsResult, error) {
	if seed == 0 {
		seed = 42
	}
	var out OperationsResult
	err := c.do(ctx, http.MethodPost, EndpointOperations,
		map[string]any{"demo": true, "seed": seed}, &out)
	if err != nil {
		return nil, err
	}
	return &out, nil
}

// AssertCloseShape validates the contract keys (headline, kpis,
// reorder_sheet[0], reply_queue[0], po_draft). Returns *Error on drift.
func AssertCloseShape(b *CloseBundle) error {
	if b == nil {
		return &Error{Status: 0, Path: EndpointClose, Attempts: 1, Msg: "nil close bundle"}
	}
	var missing []string
	if strings.TrimSpace(b.Headline) == "" {
		missing = append(missing, "headline")
	}
	// kpis subfields are structs (always present); validate golden sanity:
	// gmv/true_profit/money_at_risk are floats — check the JSON round-trip
	// carries them (non-zero gmv expected in demo).
	raw, _ := json.Marshal(b)
	var m map[string]any
	if err := json.Unmarshal(raw, &m); err != nil {
		return &Error{Status: 0, Path: EndpointClose, Attempts: 1, Msg: "re-marshal: " + err.Error()}
	}
	kpis, _ := m["kpis"].(map[string]any)
	for _, k := range []string{"gmv", "true_profit", "money_at_risk_usd"} {
		if _, ok := kpis[k]; !ok {
			missing = append(missing, "kpis."+k)
		}
	}
	if len(b.ReorderSheet) == 0 {
		missing = append(missing, "reorder_sheet[0]")
	} else {
		var r0 map[string]any
		rb, _ := json.Marshal(b.ReorderSheet[0])
		_ = json.Unmarshal(rb, &r0)
		for _, k := range []string{"product", "reorder_qty", "citation"} {
			if _, ok := r0[k]; !ok {
				missing = append(missing, "reorder_sheet[0]."+k)
			}
		}
	}
	if len(b.ReplyQueue) == 0 {
		missing = append(missing, "reply_queue[0]")
	} else {
		var q0 map[string]any
		qb, _ := json.Marshal(b.ReplyQueue[0])
		_ = json.Unmarshal(qb, &q0)
		for _, k := range []string{"draft", "citation"} {
			if _, ok := q0[k]; !ok {
				missing = append(missing, "reply_queue[0]."+k)
			}
		}
	}
	// po_draft check via raw map (struct field PODraft always exists).
	if _, ok := m["po_draft"]; !ok {
		missing = append(missing, "po_draft")
	}
	if len(missing) > 0 {
		return &Error{Status: 0, Path: EndpointClose, Attempts: 1,
			Msg: "close bundle missing contract fields: " + strings.Join(missing, ", ")}
	}
	return nil
}

// Close fetches the DAILY CLOSE bundle (profit, reorder+PO, replies, leaks).
// POST /api/v1/seller/close { demo, folder, seed, shop }.
// Validates the contract shape before returning.
func (c *Client) Close(ctx context.Context, o CloseOptions) (*CloseBundle, error) {
	seed := o.Seed
	if seed == 0 {
		seed = 42
	}
	shop := o.Shop
	if shop == "" {
		shop = "our shop"
	}
	demo := true
	if o.Folder != "" && !o.Demo {
		demo = false
	}
	if o.Demo {
		demo = true
	}
	payload := map[string]any{"demo": demo, "seed": seed, "shop": shop}
	if o.Folder != "" {
		payload["folder"] = o.Folder
	}
	var out CloseBundle
	if err := c.do(ctx, http.MethodPost, EndpointClose, payload, &out); err != nil {
		return nil, err
	}
	if err := AssertCloseShape(&out); err != nil {
		return nil, err
	}
	return &out, nil
}

// Analyze posts generic records. POST /api/v1/analyze { records }.
func (c *Client) Analyze(ctx context.Context, records []map[string]any) (*AnalyzeResult, error) {
	var out AnalyzeResult
	err := c.do(ctx, http.MethodPost, EndpointAnalyze,
		map[string]any{"records": records}, &out)
	if err != nil {
		return nil, err
	}
	return &out, nil
}

// Health checks the server. GET /health.
func (c *Client) Health(ctx context.Context) (*HealthResult, error) {
	var out HealthResult
	if err := c.do(ctx, http.MethodGet, EndpointHealth, nil, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

// ExportCSV fetches a briefing then renders CSV locally (Sheets-ready).
// Citations preserved verbatim.
func (c *Client) ExportCSV(ctx context.Context, o CloseOptions) (string, error) {
	var b *BriefingBundle
	var err error
	if o.Demo || o.Folder == "" {
		seed := o.Seed
		if seed == 0 {
			seed = 42
		}
		b, err = c.BriefingDemo(ctx, seed)
	} else {
		b, err = c.BriefingFolder(ctx, BriefingFolderOptions{Folder: o.Folder, Seed: o.Seed})
	}
	if err != nil {
		return "", err
	}
	return BriefingToCSV(b), nil
}

// CloseCSV fetches close() then renders all four artefacts locally.
func (c *Client) CloseCSV(ctx context.Context, o CloseOptions) (*CloseCSVBundle, error) {
	b, err := c.Close(ctx, o)
	if err != nil {
		return nil, err
	}
	return &CloseCSVBundle{
		CloseCSV:   CloseToCSV(b),
		ReorderCSV: ReorderToCSV(b),
		RepliesTxt: RepliesToTxt(b),
		POTxt:      b.PODraft,
	}, nil
}

// ---------------------------------------------------------------------------
// CSV/text renderers (mirror seller_export + seller_close; stdlib only;
// citations copied verbatim — file:line passthrough).
// ---------------------------------------------------------------------------

// csvCell escapes one CSV cell (quotes when needed, "" doubled).
func csvCell(v string) string {
	if strings.ContainsAny(v, ",\"\n") {
		return `"` + strings.ReplaceAll(v, `"`, `""`) + `"`
	}
	return v
}

// ftoa formats floats deterministically (trim trailing zeros like Python).
func ftoa(f float64) string {
	return strings.TrimRight(strings.TrimRight(fmt.Sprintf("%.2f", f), "0"), ".")
}

// BriefingToCSV renders briefing KPIs as CSV text.
func BriefingToCSV(b *BriefingBundle) string {
	var sb strings.Builder
	sb.WriteString("metric,value\n")
	k := b.KPIs
	kb, _ := json.Marshal(k)
	var km map[string]any
	_ = json.Unmarshal(kb, &km)
	for _, key := range []string{"gmv", "fees", "shipping", "net", "cogs",
		"true_profit", "margin_pct", "orders", "aov", "at_risk", "stockout_risk"} {
		sb.WriteString(key + "," + csvCell(fmt.Sprint(km[key])) + "\n")
	}
	sb.WriteString("best_seller," + csvCell(fmt.Sprintf("%s x%d", k.BestSeller.Product, k.BestSeller.Qty)) + "\n")
	sb.WriteString("\n")
	sb.WriteString("alert_severity,alert_message,evidence\n")
	for _, a := range b.Alerts {
		ev := ""
		if len(a.Evidence) > 0 {
			ev = a.Evidence[0] // verbatim file:line
		}
		sb.WriteString(csvCell(a.Severity) + "," + csvCell(a.Message) + "," + csvCell(ev) + "\n")
	}
	sb.WriteString("\n")
	sb.WriteString("action_n,action\n")
	for i, act := range b.Actions {
		sb.WriteString(fmt.Sprintf("%d,%s\n", i+1, csvCell(act)))
	}
	sb.WriteString("\n")
	sb.WriteString("stockout_product,on_hand,sold_7d,days_supply,citation\n")
	for _, r := range b.StockoutRisk {
		sb.WriteString(strings.Join([]string{
			csvCell(r.Product), csvCell(fmt.Sprint(r.OnHand)),
			csvCell(fmt.Sprint(r.Sold7d)), csvCell(ftoa(r.DaysSupply)),
			csvCell(r.Citation), // verbatim
		}, ",") + "\n")
	}
	return sb.String()
}

// CloseToCSV renders a CloseBundle as close.csv text.
func CloseToCSV(b *CloseBundle) string {
	var sb strings.Builder
	sb.WriteString("DAILY CLOSE," + csvCell(b.Date) + "," + csvCell(b.Headline) + "\n")
	sb.WriteString("\n")
	sb.WriteString("metric,value\n")
	kb, _ := json.Marshal(b.KPIs)
	var km map[string]any
	_ = json.Unmarshal(kb, &km)
	for _, key := range []string{"gmv", "fees", "shipping", "net", "cogs",
		"true_profit", "margin_pct", "orders", "aov", "money_at_risk_usd"} {
		sb.WriteString(key + "," + csvCell(fmt.Sprint(km[key])) + "\n")
	}
	sb.WriteString("\n")
	sb.WriteString("do_today_n,do_today\n")
	for i, t := range b.DoToday {
		sb.WriteString(fmt.Sprintf("%d,%s\n", i+1, csvCell(t)))
	}
	sb.WriteString("\n")
	sb.WriteString("product,on_hand,sold_7d,days_left,reorder_qty_14d,supplier,urgency,citation\n")
	for _, r := range b.ReorderSheet {
		sb.WriteString(strings.Join([]string{
			csvCell(r.Product), csvCell(fmt.Sprint(r.OnHand)),
			csvCell(fmt.Sprint(r.Sold7d)), csvCell(ftoa(r.DaysLeft)),
			csvCell(fmt.Sprint(r.ReorderQty)), csvCell(r.Supplier),
			csvCell(r.Urgency), csvCell(r.Citation), // verbatim file:line
		}, ",") + "\n")
	}
	sb.WriteString("\n")
	sb.WriteString("leak,amount_usd,note,evidence\n")
	for _, lk := range b.MoneyLeaks {
		amt := ""
		if lk.AmountUSD != nil {
			amt = ftoa(*lk.AmountUSD)
		}
		note := lk.Note
		if len(note) > 160 {
			note = note[:160]
		}
		sb.WriteString(strings.Join([]string{
			csvCell(lk.Leak), csvCell(amt), csvCell(note), csvCell(lk.Evidence),
		}, ",") + "\n")
	}
	return sb.String()
}

// ReorderToCSV renders the reorder sheet as reorder.csv.
func ReorderToCSV(b *CloseBundle) string {
	var sb strings.Builder
	sb.WriteString("product,on_hand,sold_7d,daily_velocity,days_left,reorder_qty_14d,supplier,urgency,citation\n")
	for _, r := range b.ReorderSheet {
		sb.WriteString(strings.Join([]string{
			csvCell(r.Product), csvCell(fmt.Sprint(r.OnHand)),
			csvCell(fmt.Sprint(r.Sold7d)), csvCell(ftoa(r.DailyVelocity)),
			csvCell(ftoa(r.DaysLeft)), csvCell(fmt.Sprint(r.ReorderQty)),
			csvCell(r.Supplier), csvCell(r.Urgency),
			csvCell(r.Citation), // verbatim
		}, ",") + "\n")
	}
	return sb.String()
}

// RepliesToTxt renders reply drafts + PO as replies.txt (copy-paste ready).
func RepliesToTxt(b *CloseBundle) string {
	var sb strings.Builder
	fmt.Fprintf(&sb, "DAILY CLOSE %s — REPLY QUEUE ($%.2f at risk)\n", b.Date, b.KPIs.MoneyAtRiskUSD)
	sb.WriteString(strings.Repeat("=", 64) + "\n\n")
	for i, q := range b.ReplyQueue {
		fmt.Fprintf(&sb, "[%d] %s — %s: %s\n", i+1, q.Priority, q.Channel, q.Customer)
		fmt.Fprintf(&sb, "    customer said: %s\n", q.Summary)
		fmt.Fprintf(&sb, "    evidence: %s\n", q.Citation) // verbatim
		draft := q.Draft
		if draft == "" {
			draft = "(see scenario action)"
		}
		fmt.Fprintf(&sb, "    COPY-PASTE DRAFT: %s\n\n", draft) // verbatim
	}
	sb.WriteString("PO DRAFT (send to supplier):\n")
	sb.WriteString(strings.Repeat("-", 64) + "\n")
	sb.WriteString(b.PODraft) // verbatim
	return sb.String()
}

// ---------------------------------------------------------------------------
// Close helpers (also see close.go for headline/reorder/reply accessors)
// ---------------------------------------------------------------------------

// CloseHeadline returns the headline verbatim (no rewriting).
func CloseHeadline(b *CloseBundle) string { return b.Headline }

// CloseTrueProfit returns kpis.true_profit.
func CloseTrueProfit(b *CloseBundle) float64 { return b.KPIs.TrueProfit }

// CloseMoneyAtRisk returns kpis.money_at_risk_usd.
func CloseMoneyAtRisk(b *CloseBundle) float64 { return b.KPIs.MoneyAtRiskUSD }

// CloseReordersToday filters urgency == "ORDER TODAY" (rows by value copy;
// Citation strings are immutable in Go — passthrough guaranteed).
func CloseReordersToday(b *CloseBundle) []ReorderLine {
	var out []ReorderLine
	for _, r := range b.ReorderSheet {
		if r.Urgency == "ORDER TODAY" {
			out = append(out, r)
		}
	}
	return out
}

// CloseP0Replies filters priority == "P0-reply-in-2h".
func CloseP0Replies(b *CloseBundle) []ReplyItem {
	var out []ReplyItem
	for _, q := range b.ReplyQueue {
		if q.Priority == "P0-reply-in-2h" {
			out = append(out, q)
		}
	}
	return out
}
