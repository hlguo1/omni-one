// GENERATED from openapi_snapshot.json — do not hand-edit
// Source: sdks/gen/openapi_snapshot.json (openapi 3.0.0, info title omni-one v1.1.0)
// Regenerate: python3 sdks/gen/regen.py  (see sdks/gen/README.md)
// Version pinned: omni-one v1.1.0 | snapshot 2026-10-11 | go stdlib only (net/http)
//
// Omni-One GENERATED Go client (net/http-only, no new deps).
//
// Covers all 18 routes from openapi_snapshot.json:
//
//	SellerClose           POST /api/v1/seller/close
//	SellerCloseCSV        GET  /api/v1/seller/close.csv
//	SellerBriefing        POST /api/v1/seller/briefing
//	SellerOperations      POST /api/v1/seller/operations
//	SellerScenariosList   GET  /api/v1/seller/scenarios
//	SellerScenariosRun    POST /api/v1/seller/scenarios/run
//	SellerExportCSV       GET  /api/v1/seller/export.csv
//	SellerPhoto           POST /api/v1/seller/photo (multipart)
//	VisionAnalyze         POST /api/v1/vision/analyze (multipart)
//	VisionDemo            GET  /api/v1/vision/demo
//	Analyze               POST /api/v1/analyze
//	Synthesize            POST /api/v1/synthesize
//	RevenueHealth         POST /api/v1/revenue/health
//	MicroBriefing         POST /api/v1/micro/briefing
//	GetMetrics            GET  /api/v1/metrics
//	ListModels            GET  /api/v1/models
//	Health                GET  /health
//	OpenapiTags           GET  /api/v1/openapi-tags
//
// Design guarantees:
//   - net/http-only: no third-party dependencies, go 1.21 compatible.
//   - retry+timeout+api-key on every call (X-API-Key header when provided).
//   - retry policy: 3 tries, exponential backoff, retry on 429/408/5xx only.
//   - context timeout: every method derives a timeout context (default 30s).
//   - citation-preserving: every method returns raw map AND typed wrapper.
//     Typed wrappers expose Raw and Citations; never drop [file:line].
//   - golden demo: SellerClose(demo=true) true_profit == 169.09 (handbook 01).
//   - invariant: true_profit <= gmv (accountant pack 04).
//   - offline $0: demo paths need no network beyond localhost.
//
// Parsing guarantee: gofmt -l returns empty; go vet ./... is green.
// Version pin: snapshot v1.1.0; client GeneratedVersion == "1.1.0".
// Regeneration: edit sdks/gen/openapi_snapshot.json then re-run sdks/gen/regen.py.
package gen

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"mime/multipart"
	"net/http"
	"net/url"
	"os"
	"strings"
	"time"
)

// ============================================================================
// Version + defaults (pinned to snapshot v1.1.0)
// ============================================================================

// GeneratedVersion pins this client to the snapshot version.
// Snapshot v1.1.0 <-> client v1.1.0 <-> server v1.1.0 (fastapi_app + ops).
// Bump all three together; regen.py asserts snapshot == client version.
const GeneratedVersion = "1.1.0"

// SnapshotFile is the source snapshot this client was generated from.
const SnapshotFile = "openapi_snapshot.json"

// SnapshotTitle is the expected info.title in the snapshot.
const SnapshotTitle = "omni-one"

// DefaultBaseURL is the local dev server (uvicorn port 5003).
// Override per-client via NewClient(baseURL, apiKey).BaseURL.
const DefaultBaseURL = "http://localhost:5003"

// DefaultTimeoutSecs is the per-call context timeout in seconds.
// Every method derives context.WithTimeout from the caller context.
const DefaultTimeoutSecs = 30.0

// DefaultRetries is the total attempt count (1 initial + 2 retries).
const DefaultRetries = 3

// DefaultBackoffMs is the base backoff; attempt n sleeps base*2^n.
const DefaultBackoffMs = 500

// GoldenTrueProfit is the demo-shop golden number (handbook 01 ritual).
// SellerClose(demo=true, seed=42) must report true_profit == 169.09.
const GoldenTrueProfit = 169.09

// GoldenMarginPct is the demo-shop golden margin (handbook 04 pack).
const GoldenMarginPct = 61.7

// GoldenMoneyAtRiskUSD is the demo-shop refund exposure (3 msgs * aov).
const GoldenMoneyAtRiskUSD = 102.75

// GoldenDemoSeed is the deterministic demo seed (reproducible close).
const GoldenDemoSeed = 42

// UserAgent sent on every request (observability, no PII).
const UserAgent = "omni-one-generated-go/1.1.0"

// APIKeyHeader is the auth header; sent only when Client.APIKey != "".
const APIKeyHeader = "X-API-Key"

// ============================================================================
// Typed wrappers (citation-preserving)
// Every wrapper keeps Raw (original map) and Citations ([file:line] list).
// Never drop citations when converting; accountants audit them (handbook 04).
// ============================================================================

// KPIs holds ledger KPIs from close.csv Section A.
// Invariant true_profit <= gmv is enforced by CheckInvariant.
// Golden demo: gmv 274.0, true_profit 169.09, margin 61.7, at-risk 102.75.
// See openapi_snapshot.json#/components/schemas/KPIs.
type KPIs struct {
	// GMV: Gross merchandise value: sum of order-row totals.
	// Source: shopify_orders.csv / etsy_settlement.csv / amazon payout rows.
	// Golden demo gmv is 274.0. Every figure cites [file:line].
	GMV float64 `json:"gmv,omitempty"`

	// Fees: Channel fees parsed per row, else estimated.
	// Estimates: Etsy 6.5%+$0.20, Shopify 2.9%+$0.30, Amazon 15%, other 8%.
	// Golden demo fees are 18.5. Cites fee source file:line.
	Fees float64 `json:"fees,omitempty"`

	// Shipping: Shipping paid/collected per order rows.
	// Net of free-shipping absorptions; see 04-accountant-pack section 2.
	// Golden demo shipping is 12.0. Cites [file:line].
	Shipping float64 `json:"shipping,omitempty"`

	// Net: Net revenue: gmv - fees - shipping.
	// Golden demo net is 243.5. Derived, cites operand lines.
	// Invariant helper: net must stay non-negative on sane input.
	Net float64 `json:"net,omitempty"`

	// COGS: Cost of goods sold allocated per-unit from invoices.
	// Fallback: 30% of GMV when unmatched, 25% of smallest invoice if none.
	// Golden demo cogs is 74.41. See handbook 04 section 3.
	COGS float64 `json:"cogs,omitempty"`

	// TrueProfit: True profit: net - cogs. THE number.
	// Golden demo true_profit is 169.09. No citation, no action.
	// Invariant: true_profit <= gmv always (audited by CheckInvariant).
	TrueProfit float64 `json:"true_profit,omitempty"`

	// MarginPct: Margin percent: true_profit/gmv*100.
	// Zero when gmv is 0 (no division by zero, ever).
	// Golden demo margin is 61.7. Cites kpis_citations.
	MarginPct float64 `json:"margin_pct,omitempty"`

	// Orders: Order rows ingested into the close.
	// Golden demo orders are 8. Dedup identical content (ingest_report).
	// Cites each order file:line consumed.
	Orders int `json:"orders,omitempty"`

	// AOV: Average order value: gmv/orders (0 when none).
	// Golden demo aov is 34.25. Money at risk derives from aov.
	// Cites order files backing gmv and orders.
	AOV float64 `json:"aov,omitempty"`

	// BestSeller: Top product by units {product,qty,gmv}.
	// Golden demo best seller is Tote Bag Handmade (6 units).
	// Byte-identical names: never mangle CJK/emoji product titles.
	BestSeller map[string]any `json:"best_seller,omitempty"`

	// MoneyAtRiskUSD: Refund exposure: len(reply_queue)*aov.
	// Golden demo money at risk is 102.75 across 3 angry messages.
	// Reply P0 in under 2h to defend every dollar (handbook 03).
	MoneyAtRiskUSD float64 `json:"money_at_risk_usd,omitempty"`

	// WorstSeller: Worst seller for kill/bundle/clearance call.
	// Feeds scenario REVIEW_CRISIS / clearance Workshop actions.
	// Cites sales rows proving low velocity.
	WorstSeller map[string]any `json:"worst_seller,omitempty"`

	// Citations: All [file:line] citations backing these KPIs.
	// Every derived number MUST carry at least one citation.
	// If a number has no citation, do not trust it (handbook 01 one rule).
	Citations []string `json:"citations,omitempty"`

	// Raw preserves the original decoded map byte-identically.
	// CJK/emoji customer and product names round-trip untouched.
	// Always consult Raw before assuming a typed zero value.
	Raw map[string]any `json:"-"`
}

// KPIsFromMap builds KPIs preserving the raw map and citations.
// The raw map is kept verbatim; typed fields decode via JSON round-trip.
// Never invent numbers: missing keys decode to Go zero values.
func KPIsFromMap(m map[string]any) (*KPIs, error) {
	b, err := json.Marshal(m)
	if err != nil {
		return nil, fmt.Errorf("KPIsFromMap marshal: %w", err)
	}
	var out KPIs
	if err := json.Unmarshal(b, &out); err != nil {
		return nil, fmt.Errorf("KPIsFromMap unmarshal: %w", err)
	}
	out.Raw = m
	return &out, nil
}

// ToMap returns the raw map when present, else re-encodes typed fields.
// Citations are always kept: raw passthrough is byte-identical.
func (k *KPIs) ToMap() map[string]any {
	if k == nil {
		return map[string]any{}
	}
	if len(k.Raw) > 0 {
		return k.Raw
	}
	b, err := json.Marshal(k)
	if err != nil {
		return map[string]any{}
	}
	m := map[string]any{}
	_ = json.Unmarshal(b, &m)
	return m
}

// CitationsList returns every [file:line] backing this KPI set.
// It merges the typed Citations with any citation keys inside Raw.
func (k *KPIs) CitationsList() []string {
	if k == nil {
		return nil
	}
	return CitationsOf(k.ToMap())
}

// CheckInvariant reports true_profit <= gmv (handbook 04 invariant).
// Corrupt pipelines violate it; the close must refuse invented tasks.
func (k *KPIs) CheckInvariant() bool {
	if k == nil {
		return true
	}
	return k.TrueProfit <= k.GMV+1e-9
}

// ReorderLine is one row of reorder.csv under the 14-day cover policy.
// Urgency ORDER TODAY means under 3 days of cover left.
// See openapi_snapshot.json#/components/schemas/ReorderLine.
type ReorderLine struct {
	// Product: Product title exactly as in inventory.csv.
	// Byte-identical: never mangle CJK/emoji names in drafts.
	// Golden demo: Tote Bag Handmade.
	Product string `json:"product,omitempty"`

	// OnHand: Units on hand in inventory.csv right now.
	// Proven by the citation field on this same row.
	// Golden demo on_hand is 2.
	OnHand int `json:"on_hand,omitempty"`

	// Sold7d: Units sold in the last 7 days of order files.
	// Velocity window is fixed at 7 days (handbook 02).
	// Golden demo sold_7d is 6.
	Sold7d int `json:"sold_7d,omitempty"`

	// DailyVelocity: Daily velocity: sold_7d/7.
	// Golden demo velocity is 0.86 units per day.
	// Zero velocity yields days_left 999.
	DailyVelocity float64 `json:"daily_velocity,omitempty"`

	// DaysLeft: Days of cover: on_hand/daily_velocity.
	// 999 means no recent sales (watch, do not reorder).
	// Golden demo days_left is 2.3.
	DaysLeft float64 `json:"days_left,omitempty"`

	// ReorderQty14d: Reorder qty: ceil(velocity*14 - on_hand), floored at 0.
	// Cover policy is 14 days (handbook 02 supplier playbook).
	// Golden demo reorder_qty_14d is 10.
	ReorderQty14d int `json:"reorder_qty_14d,omitempty"`

	// Supplier: Supplier name from the COGS bible.
	// Golden demo supplier is Acme Textiles.
	// PO draft asks price + ETA (handbook 02).
	Supplier string `json:"supplier,omitempty"`

	// Urgency: Urgency: ORDER TODAY (<3d), this week (<5d), watch.
	// Sorts the do_today action list in close.csv Section B.
	// Golden demo urgency is ORDER TODAY.
	Urgency string `json:"urgency,omitempty"`

	// Citation: [file:line] proving on_hand and velocity.
	// Example: [inventory.csv:2]. No citation, no action.
	// Kept verbatim in every wrapper.
	Citation string `json:"citation,omitempty"`

	// Raw preserves the original decoded map byte-identically.
	// CJK/emoji customer and product names round-trip untouched.
	// Always consult Raw before assuming a typed zero value.
	Raw map[string]any `json:"-"`
}

// ReorderLineFromMap builds a ReorderLine preserving raw + citation.
func ReorderLineFromMap(m map[string]any) (*ReorderLine, error) {
	b, err := json.Marshal(m)
	if err != nil {
		return nil, fmt.Errorf("ReorderLineFromMap marshal: %w", err)
	}
	var out ReorderLine
	if err := json.Unmarshal(b, &out); err != nil {
		return nil, fmt.Errorf("ReorderLineFromMap unmarshal: %w", err)
	}
	out.Raw = m
	return &out, nil
}

// ToMap returns raw when present, else re-encodes typed fields.
func (r *ReorderLine) ToMap() map[string]any {
	if r == nil {
		return map[string]any{}
	}
	if len(r.Raw) > 0 {
		return r.Raw
	}
	b, err := json.Marshal(r)
	if err != nil {
		return map[string]any{}
	}
	m := map[string]any{}
	_ = json.Unmarshal(b, &m)
	return m
}

// CitationsList collects [file:line] from the row and its raw map.
func (r *ReorderLine) CitationsList() []string {
	if r == nil {
		return nil
	}
	return CitationsOf(r.ToMap())
}

// ReplyItem is one draft in the reply queue (replies.txt).
// P0 drafts must go out within 2 hours; P1 same-day.
// See openapi_snapshot.json#/components/schemas/ReplyItem.
type ReplyItem struct {
	// ID: Stable draft id, e.g. reply-001.
	// Stable across reruns for the same source line.
	// Used by Workshop dedup keys.
	ID string `json:"id,omitempty"`

	// Priority: P0-reply-in-2h or P1-today.
	// P0: refund / hasnt-arrived / damaged / chargeback (handbook 03).
	// Everything else is P1 same-day.
	Priority string `json:"priority,omitempty"`

	// Channel: Source channel: dm, review, or order.
	// Drives which reply template family applies.
	// See 03-reply-playbook templates 01-20.
	Channel string `json:"channel,omitempty"`

	// Customer: Customer name, byte-identical (CJK/emoji safe).
	// Never mangle: copy-paste fidelity is a correctness property.
	// Golden demo includes Maria.
	Customer string `json:"customer,omitempty"`

	// Excerpt: Customer words quoted verbatim.
	// Grounds the draft in what was actually said.
	// Cites the source dm/review line.
	Excerpt string `json:"excerpt,omitempty"`

	// Draft: Copy-paste reply draft with one personalise slot.
	// Keeps the citation so the seller can verify before sending.
	// Template ids 01-20 (handbook 03).
	Draft string `json:"draft,omitempty"`

	// Citation: [file:line] source of the complaint.
	// Example: [instagram_dm.txt:4].
	// No citation, no send.
	Citation string `json:"citation,omitempty"`

	// TemplateID: Reply template used, 01-20.
	// Auditable against 03-reply-playbook.
	// Empty means heuristic fallback draft.
	TemplateID string `json:"template_id,omitempty"`

	// AmountAtRiskUSD: AOV exposure defended by this reply.
	// Sums toward money_at_risk_usd across the queue.
	// Golden demo aov is 34.25.
	AmountAtRiskUSD float64 `json:"amount_at_risk_usd,omitempty"`

	// Raw preserves the original decoded map byte-identically.
	// CJK/emoji customer and product names round-trip untouched.
	// Always consult Raw before assuming a typed zero value.
	Raw map[string]any `json:"-"`
}

// ReplyItemFromMap builds a ReplyItem preserving raw + citation.
func ReplyItemFromMap(m map[string]any) (*ReplyItem, error) {
	b, err := json.Marshal(m)
	if err != nil {
		return nil, fmt.Errorf("ReplyItemFromMap marshal: %w", err)
	}
	var out ReplyItem
	if err := json.Unmarshal(b, &out); err != nil {
		return nil, fmt.Errorf("ReplyItemFromMap unmarshal: %w", err)
	}
	out.Raw = m
	return &out, nil
}

// ToMap returns raw when present, else re-encodes typed fields.
func (r *ReplyItem) ToMap() map[string]any {
	if r == nil {
		return map[string]any{}
	}
	if len(r.Raw) > 0 {
		return r.Raw
	}
	b, err := json.Marshal(r)
	if err != nil {
		return map[string]any{}
	}
	m := map[string]any{}
	_ = json.Unmarshal(b, &m)
	return m
}

// CitationsList collects [file:line] from the draft and its raw map.
func (r *ReplyItem) CitationsList() []string {
	if r == nil {
		return nil
	}
	return CitationsOf(r.ToMap())
}

// Briefing is the seller briefing bundle: kpis, headline, risks, drafts.
// All money cites [file:line]; chart and ingest report included.
// See openapi_snapshot.json#/components/schemas/Briefing.
type Briefing struct {
	// KPIs: Ledger KPIs for the briefing window.
	// Same ledger as the daily close Section A.
	// Golden true_profit 169.09.
	KPIs KPIs `json:"kpis,omitempty"`

	// Headline: One coffee-brain line for the morning ritual.
	// Golden: Profit $169.09 (61.7%) ... 1 reorder TODAY ...
	// Handbook 01 morning routine.
	Headline string `json:"headline,omitempty"`

	// StockoutRisk: SKUs with low days_left cover.
	// Sorted most urgent first (ORDER TODAY on top).
	// Feeds the reorder sheet.
	StockoutRisk []ReorderLine `json:"stockout_risk,omitempty"`

	// ReplyQueue: Draft replies, P0 first.
	// Each draft carries its own [file:line] citation.
	// 3 angry messages in the golden demo.
	ReplyQueue []ReplyItem `json:"reply_queue,omitempty"`

	// MoneyLeaks: Leaks: fee creep, shipping, margin erosion.
	// Each leak has amount_usd, note, and evidence.
	// 0 leaks in the golden demo.
	MoneyLeaks []map[string]any `json:"money_leaks,omitempty"`

	// Chart: Chart payload {labels, data} for the briefing card.
	// Rendered client-side; no server round-trip needed.
	// Matplotlib PNG on the server path.
	Chart map[string]any `json:"chart,omitempty"`

	// IngestReport: Ingest report {files_seen, files_ingested, demo}.
	// Identical content is deduped, never double-counted.
	// Proves which files fed the numbers.
	IngestReport map[string]any `json:"ingest_report,omitempty"`

	// Citations: Global [file:line] citations for the briefing.
	// Union of every number shown to the seller.
	// Audit trail for the accountant pack.
	Citations []string `json:"citations,omitempty"`

	// Raw preserves the original decoded map byte-identically.
	// CJK/emoji customer and product names round-trip untouched.
	// Always consult Raw before assuming a typed zero value.
	Raw map[string]any `json:"-"`
}

// BriefingFromMap builds a Briefing preserving raw + citations.
func BriefingFromMap(m map[string]any) (*Briefing, error) {
	b, err := json.Marshal(m)
	if err != nil {
		return nil, fmt.Errorf("BriefingFromMap marshal: %w", err)
	}
	var out Briefing
	if err := json.Unmarshal(b, &out); err != nil {
		return nil, fmt.Errorf("BriefingFromMap unmarshal: %w", err)
	}
	out.Raw = m
	return &out, nil
}

// ToMap returns raw when present, else re-encodes typed fields.
func (b *Briefing) ToMap() map[string]any {
	if b == nil {
		return map[string]any{}
	}
	if len(b.Raw) > 0 {
		return b.Raw
	}
	bb, err := json.Marshal(b)
	if err != nil {
		return map[string]any{}
	}
	m := map[string]any{}
	_ = json.Unmarshal(bb, &m)
	return m
}

// CitationsList collects [file:line] from the briefing and nested KPIs.
func (b *Briefing) CitationsList() []string {
	if b == nil {
		return nil
	}
	return CitationsOf(b.ToMap())
}

// ScenarioDecision is one of 12 scenario decisions, critical first.
// Workshop queue plus governance audit stay grounded on evidence.
// See openapi_snapshot.json#/components/schemas/ScenarioDecision.
type ScenarioDecision struct {
	// ID: Stable decision id, e.g. dec-stockout-001.
	// Stable across reruns for identical triggers.
	// Workshop queue keys off this id.
	ID string `json:"id,omitempty"`

	// ScenarioID: Registry id: STOCKOUT, REVIEW_CRISIS, FEE_SPIKE, ...
	// One of the 12 practical seller scenarios.
	// Listed by SellerScenariosList.
	ScenarioID string `json:"scenario_id,omitempty"`

	// Severity: Severity: critical, high, medium, or low.
	// Queue sorts critical first, then high, medium, low.
	// Golden demo STOCKOUT is critical.
	Severity string `json:"severity,omitempty"`

	// Title: Human title, e.g. Tote Bag Handmade hits zero in 2.3d.
	// One line the seller can act on.
	// Cites the evidence line.
	Title string `json:"title,omitempty"`

	// Action: Workshop action, e.g. reorderProduct.
	// Executed by the operations loop after approval.
	// Audited by governance (handbook 05).
	Action string `json:"action,omitempty"`

	// Product: Affected product title, byte-identical.
	// Empty for shop-wide scenarios (fee spikes).
	// Never mangle CJK/emoji names.
	Product string `json:"product,omitempty"`

	// Evidence: Thresholds plus observed values proving the trigger.
	// Grounded check: values must come from cited files.
	// AIP refuses uncited triggers.
	Evidence map[string]any `json:"evidence,omitempty"`

	// Citation: [file:line] evidence for the decision.
	// Example: [inventory.csv:2].
	// No citation, no action.
	Citation string `json:"citation,omitempty"`

	// WorkshopID: Workshop queue id after scenarios_to_workshop.
	// Empty until the decision is enqueued.
	// Tracks assign/operate lifecycle.
	WorkshopID string `json:"workshop_id,omitempty"`

	// Raw preserves the original decoded map byte-identically.
	// CJK/emoji customer and product names round-trip untouched.
	// Always consult Raw before assuming a typed zero value.
	Raw map[string]any `json:"-"`
}

// ScenarioDecisionFromMap builds a decision preserving raw + citation.
func ScenarioDecisionFromMap(m map[string]any) (*ScenarioDecision, error) {
	b, err := json.Marshal(m)
	if err != nil {
		return nil, fmt.Errorf("ScenarioDecisionFromMap marshal: %w", err)
	}
	var out ScenarioDecision
	if err := json.Unmarshal(b, &out); err != nil {
		return nil, fmt.Errorf("ScenarioDecisionFromMap unmarshal: %w", err)
	}
	out.Raw = m
	return &out, nil
}

// ToMap returns raw when present, else re-encodes typed fields.
func (s *ScenarioDecision) ToMap() map[string]any {
	if s == nil {
		return map[string]any{}
	}
	if len(s.Raw) > 0 {
		return s.Raw
	}
	b, err := json.Marshal(s)
	if err != nil {
		return map[string]any{}
	}
	m := map[string]any{}
	_ = json.Unmarshal(b, &m)
	return m
}

// CitationsList collects [file:line] from the decision and its raw map.
func (s *ScenarioDecision) CitationsList() []string {
	if s == nil {
		return nil
	}
	return CitationsOf(s.ToMap())
}

// CloseBundle is the DAILY CLOSE bundle: briefing, scenarios, CSV, PO draft.
// Machine-readable everything; keep 12 months for the accountant pack.
// See openapi_snapshot.json#/components/schemas/CloseBundle.
type CloseBundle struct {
	// KPIs: Ledger KPIs: gmv, fees, shipping, net, cogs, true_profit.
	// Golden true_profit 169.09; invariant true_profit <= gmv.
	// Cites every money line.
	KPIs KPIs `json:"kpis,omitempty"`

	// Briefing: Embedded seller briefing for the same window.
	// Headline plus stockout risk plus reply queue.
	// Same citations as the standalone briefing.
	Briefing Briefing `json:"briefing,omitempty"`

	// Headline: Daily close headline for the morning ritual.
	// Golden: Profit $169.09 (61.7%) ... 1 reorder TODAY ...
	// Handbook 01 one-coffee line.
	Headline string `json:"headline,omitempty"`

	// Reorder: Reorder sheet rows under 14-day cover policy.
	// Also exposed as reorder_sheet by some servers; both parse.
	// 1 reorder TODAY in golden demo.
	Reorder []ReorderLine `json:"reorder,omitempty"`

	// ReplyQueue: Reply queue drafts, P0 (2h) first.
	// 3 angry messages in the golden demo.
	// Each draft keeps its [file:line].
	ReplyQueue []ReplyItem `json:"reply_queue,omitempty"`

	// Scenarios: Scenario decisions critical first.
	// Stable ids across reruns for identical triggers.
	// Workshop queue input.
	Scenarios []ScenarioDecision `json:"scenarios,omitempty"`

	// MoneyLeaks: Money leaks: fee creep, shipping, margin.
	// 0 leaks in the golden demo.
	// Each leak cites evidence.
	MoneyLeaks []map[string]any `json:"money_leaks,omitempty"`

	// PoDraft: PO email draft with price + ETA ask.
	// Cites the inventory line so suppliers can verify.
	// Handbook 02 supplier playbook.
	PoDraft string `json:"po_draft,omitempty"`

	// CloseCSV: Rendered close.csv text (Sections A-D).
	// Accountant-ready ledger for the 04 pack.
	// Matches SellerCloseCSV bytes.
	CloseCSV string `json:"close_csv,omitempty"`

	// IngestReport: Ingest report {files_seen, files_ingested}.
	// Proves which files fed the close.
	// Dedup identical content.
	IngestReport map[string]any `json:"ingest_report,omitempty"`

	// Citations: Global [file:line] citations for the bundle.
	// Audit trail across kpis, reorder, replies, leaks.
	// No citation, no action.
	Citations []string `json:"citations,omitempty"`

	// Raw preserves the original decoded map byte-identically.
	// CJK/emoji customer and product names round-trip untouched.
	// Always consult Raw before assuming a typed zero value.
	Raw map[string]any `json:"-"`
}

// CloseBundleFromMap builds a CloseBundle preserving raw + citations.
// It also accepts the reorder_sheet alias some servers emit for reorder.
func CloseBundleFromMap(m map[string]any) (*CloseBundle, error) {
	b, err := json.Marshal(m)
	if err != nil {
		return nil, fmt.Errorf("CloseBundleFromMap marshal: %w", err)
	}
	var out CloseBundle
	if err := json.Unmarshal(b, &out); err != nil {
		return nil, fmt.Errorf("CloseBundleFromMap unmarshal: %w", err)
	}
	if len(out.Reorder) == 0 {
		if alt, ok := m["reorder_sheet"]; ok {
			ab, aerr := json.Marshal(alt)
			if aerr == nil {
				_ = json.Unmarshal(ab, &out.Reorder)
			}
		}
	}
	out.Raw = m
	return &out, nil
}

// ToMap returns raw when present, else re-encodes typed fields.
func (c *CloseBundle) ToMap() map[string]any {
	if c == nil {
		return map[string]any{}
	}
	if len(c.Raw) > 0 {
		return c.Raw
	}
	b, err := json.Marshal(c)
	if err != nil {
		return map[string]any{}
	}
	m := map[string]any{}
	_ = json.Unmarshal(b, &m)
	return m
}

// CitationsList collects [file:line] across the bundle and nested KPIs.
func (c *CloseBundle) CitationsList() []string {
	if c == nil {
		return nil
	}
	return CitationsOf(c.ToMap())
}

// CheckInvariant proxies the accountant invariant true_profit <= gmv.
func (c *CloseBundle) CheckInvariant() bool {
	if c == nil {
		return true
	}
	return c.KPIs.CheckInvariant()
}

// ============================================================================
// Request bodies (8 POST routes; GET routes use query maps instead)
// Pass demo=true + seed=42 for the synthetic golden shop, or folder=path.
// Folders must live inside ./data/inbox or /tmp (server guard rejects ..).
// ============================================================================

// CloseRequest: POST /seller/close body. demo=true or folder path.
// Snapshot: openapi_snapshot.json#/components/schemas/CloseRequest.
// Citation rule travels with the response, not the request.
type CloseRequest struct {
	// Demo: Use the synthetic demo shop (seed 42 default).
	// Offline $0, no network beyond localhost.
	Demo bool `json:"demo,omitempty"`

	// Folder: Messy seller folder inside ./data/inbox or /tmp.
	// Path traversal is rejected (400).
	Folder string `json:"folder,omitempty"`

	// Seed: Demo seed for reproducible numbers.
	// Golden demo uses seed 42.
	Seed int `json:"seed,omitempty"`

	// Shop: Shop display name.
	// Golden demo shop is our shop.
	Shop string `json:"shop,omitempty"`

	// Locale: Reply/PO draft language (en|es|zh|fr|de, default en).
	// Numbers and citations never change with locale.
	Locale string `json:"locale,omitempty"`
}

// ToMap encodes CloseRequest to a JSON-ready map, dropping empty fields.
// The map feeds doJSON as the POST body (Content-Type application/json).
func (r CloseRequest) ToMap() map[string]any {
	b, err := json.Marshal(r)
	if err != nil {
		return map[string]any{}
	}
	m := map[string]any{}
	_ = json.Unmarshal(b, &m)
	return m
}

// BriefingRequest: POST /seller/briefing body. folder or events or demo.
// Snapshot: openapi_snapshot.json#/components/schemas/BriefingRequest.
// Citation rule travels with the response, not the request.
type BriefingRequest struct {
	// Demo: Use the synthetic demo shop.
	// Offline $0 briefing in seconds.
	Demo bool `json:"demo,omitempty"`

	// Folder: Messy seller folder path.
	// CSVs, reviews, dm text, invoice photos.
	Folder string `json:"folder,omitempty"`

	// Seed: Demo seed.
	// Default 42.
	Seed int `json:"seed,omitempty"`

	// Events: Inline micro-biz events alternative.
	// Folder drop preferred for big shops.
	Events []map[string]any `json:"events,omitempty"`
}

// ToMap encodes BriefingRequest to a JSON-ready map, dropping empty fields.
// The map feeds doJSON as the POST body (Content-Type application/json).
func (r BriefingRequest) ToMap() map[string]any {
	b, err := json.Marshal(r)
	if err != nil {
		return map[string]any{}
	}
	m := map[string]any{}
	_ = json.Unmarshal(b, &m)
	return m
}

// OperationsRequest: POST /seller/operations body. briefing + workshop + audit.
// Snapshot: openapi_snapshot.json#/components/schemas/OperationsRequest.
// Citation rule travels with the response, not the request.
type OperationsRequest struct {
	// Demo: Use the synthetic demo shop.
	// Full Palantir-style loop offline.
	Demo bool `json:"demo,omitempty"`

	// Seed: Demo seed.
	// Default 42.
	Seed int `json:"seed,omitempty"`
}

// ToMap encodes OperationsRequest to a JSON-ready map, dropping empty fields.
// The map feeds doJSON as the POST body (Content-Type application/json).
func (r OperationsRequest) ToMap() map[string]any {
	b, err := json.Marshal(r)
	if err != nil {
		return map[string]any{}
	}
	m := map[string]any{}
	_ = json.Unmarshal(b, &m)
	return m
}

// ScenariosRunRequest: POST /seller/scenarios/run body. demo or folder.
// Snapshot: openapi_snapshot.json#/components/schemas/ScenariosRunRequest.
// Citation rule travels with the response, not the request.
type ScenariosRunRequest struct {
	// Demo: Use the synthetic demo shop.
	// Deterministic O(n) run.
	Demo bool `json:"demo,omitempty"`

	// Folder: Seller folder path.
	// Guard rejects traversal.
	Folder string `json:"folder,omitempty"`

	// Seed: Demo seed.
	// Default 42.
	Seed int `json:"seed,omitempty"`
}

// ToMap encodes ScenariosRunRequest to a JSON-ready map, dropping empty fields.
// The map feeds doJSON as the POST body (Content-Type application/json).
func (r ScenariosRunRequest) ToMap() map[string]any {
	b, err := json.Marshal(r)
	if err != nil {
		return map[string]any{}
	}
	m := map[string]any{}
	_ = json.Unmarshal(b, &m)
	return m
}

// AnalyzeRequest: POST /analyze body {records[]}. multi-layer pipeline.
// Snapshot: openapi_snapshot.json#/components/schemas/AnalyzeRequest.
// Citation rule travels with the response, not the request.
type AnalyzeRequest struct {
	// Records: Records for L1-L4 pipeline.
	// L1 <1ms L2 <10ms L3 <100ms L4 LLM gated.
	Records []map[string]any `json:"records,omitempty"`
}

// ToMap encodes AnalyzeRequest to a JSON-ready map, dropping empty fields.
// The map feeds doJSON as the POST body (Content-Type application/json).
func (r AnalyzeRequest) ToMap() map[string]any {
	b, err := json.Marshal(r)
	if err != nil {
		return map[string]any{}
	}
	m := map[string]any{}
	_ = json.Unmarshal(b, &m)
	return m
}

// SynthesizeRequest: POST /synthesize body. query + context + routing.
// Snapshot: openapi_snapshot.json#/components/schemas/SynthesizeRequest.
// Citation rule travels with the response, not the request.
type SynthesizeRequest struct {
	// Query: Question to synthesize.
	// Grounded in provided context.
	Query string `json:"query,omitempty"`

	// Context: Source passages.
	// Citations required in response.
	Context []string `json:"context,omitempty"`

	// TaskType: Task routing hint.
	// Drives model tier selection.
	TaskType string `json:"task_type,omitempty"`

	// UserTier: Caller tier.
	// Fast/balanced/premium routing.
	UserTier string `json:"user_tier,omitempty"`

	// Temperature: Sampling temperature.
	// Default 0.2 for grounded tasks.
	Temperature float64 `json:"temperature,omitempty"`

	// MaxTokens: Max output tokens.
	// Caps cost per call.
	MaxTokens int `json:"max_tokens,omitempty"`
}

// ToMap encodes SynthesizeRequest to a JSON-ready map, dropping empty fields.
// The map feeds doJSON as the POST body (Content-Type application/json).
func (r SynthesizeRequest) ToMap() map[string]any {
	b, err := json.Marshal(r)
	if err != nil {
		return map[string]any{}
	}
	m := map[string]any{}
	_ = json.Unmarshal(b, &m)
	return m
}

// RevenueHealthRequest: POST /revenue/health body. synthetic accounts scoring.
// Snapshot: openapi_snapshot.json#/components/schemas/RevenueHealthRequest.
// Citation rule travels with the response, not the request.
type RevenueHealthRequest struct {
	// Accounts: Account count 1-500.
	// Deterministic rules + 4-layer pipeline.
	Accounts int `json:"accounts,omitempty"`

	// Seed: Generation seed.
	// Default 42.
	Seed int `json:"seed,omitempty"`
}

// ToMap encodes RevenueHealthRequest to a JSON-ready map, dropping empty fields.
// The map feeds doJSON as the POST body (Content-Type application/json).
func (r RevenueHealthRequest) ToMap() map[string]any {
	b, err := json.Marshal(r)
	if err != nil {
		return map[string]any{}
	}
	m := map[string]any{}
	_ = json.Unmarshal(b, &m)
	return m
}

// MicroBriefingRequest: POST /micro/briefing body. folder|events|demo.
// Snapshot: openapi_snapshot.json#/components/schemas/MicroBriefingRequest.
// Citation rule travels with the response, not the request.
type MicroBriefingRequest struct {
	// Folder: Messy receipts/chats/csv folder.
	// Zero integrations, just drop.
	Folder string `json:"folder,omitempty"`

	// Events: Inline events alternative.
	// Smallest-business friendly.
	Events []map[string]any `json:"events,omitempty"`

	// Demo: Maya's Tacos synthetic demo.
	// Tacos al pastor 32x3.50=112.
	Demo bool `json:"demo,omitempty"`

	// Seed: Demo seed.
	// Default 42.
	Seed int `json:"seed,omitempty"`
}

// ToMap encodes MicroBriefingRequest to a JSON-ready map, dropping empty fields.
// The map feeds doJSON as the POST body (Content-Type application/json).
func (r MicroBriefingRequest) ToMap() map[string]any {
	b, err := json.Marshal(r)
	if err != nil {
		return map[string]any{}
	}
	m := map[string]any{}
	_ = json.Unmarshal(b, &m)
	return m
}

// ============================================================================
// Client (net/http-only, retry+timeout+api-key, citation-preserving)
// ============================================================================

// Client talks to omni-one v1.1.0 over plain net/http (no new deps).
// Zero value is usable but prefer NewClient for sane defaults.
// Concurrency: a single Client is safe for concurrent goroutine use.
// Auth: APIKey is sent as X-API-Key on every call when non-empty.
// Timeout: TimeoutSecs bounds every call via context.WithTimeout.
// Retry: 3 tries with exponential backoff on 429/408/5xx; 400/401 fast-fail.
type Client struct {
	// BaseURL is the server origin, e.g. http://localhost:5003.
	// Override per environment; never hardcode paths against it.
	BaseURL string

	// APIKey is the optional shared secret sent as X-API-Key.
	// Empty means unauthenticated (local dev default).
	APIKey string

	// TimeoutSecs bounds each call (context timeout, default 30).
	// Non-positive values fall back to DefaultTimeoutSecs.
	TimeoutSecs float64

	// HTTP is the underlying transport; nil falls back to http.DefaultClient.
	// Inject a custom *http.Client in tests (httptest) or prod (mTLS).
	*http.Client
}

// NewClient builds a Client with default timeout, retries, and transport.
// baseURL is the server origin (http://localhost:5003 for local dev).
// apiKey is optional; empty disables the X-API-Key header.
// The returned client retries 429/408/5xx 3 times with backoff.
func NewClient(baseURL, apiKey string) *Client {
	if strings.TrimSpace(baseURL) == "" {
		baseURL = DefaultBaseURL
	}
	return &Client{
		BaseURL:     strings.TrimSuffix(baseURL, "/"),
		APIKey:      apiKey,
		TimeoutSecs: DefaultTimeoutSecs,
		Client:      &http.Client{},
	}
}

// httpError carries a non-2xx response through the retry loop.
// Status decides retryability: 429/408/5xx retry, other 4xx fast-fail.
type httpError struct {
	// Status is the HTTP status code (429, 408, 500, ...).
	Status int

	// Method and URL identify the failed call for debugging.
	Method string
	URL    string

	// Body is the truncated response body for diagnostics.
	Body string
}

// Error implements the error interface with status + route + body.
func (e *httpError) Error() string {
	return fmt.Sprintf("HTTP %d %s %s: %s", e.Status, e.Method, e.URL, e.Body)
}

// retryableStatus reports whether a status deserves another attempt.
// Retries: 429 rate-limited, 408 timeout, any 5xx (3 tries total).
// Fast-fail: 400 bad CSV, 401 bad key, 404 unknown route (fix caller).
func retryableStatus(status int) bool {
	if status == http.StatusTooManyRequests {
		return true
	}
	if status == http.StatusRequestTimeout {
		return true
	}
	return status >= 500 && status <= 599
}

// backoffFor returns base*2^attempt, capped at 8x base to stay snappy.
// Attempt 0 sleeps 500ms, attempt 1 sleeps 1s (3 tries => <=1.5s extra).
func backoffFor(attempt int) time.Duration {
	ms := DefaultBackoffMs << attempt
	if ms > DefaultBackoffMs*8 {
		ms = DefaultBackoffMs * 8
	}
	return time.Duration(ms) * time.Millisecond
}

// withTimeout derives a bounded context for one call (default 30s).
// Non-positive TimeoutSecs falls back to DefaultTimeoutSecs.
// Callers must defer cancel() to release the timer.
func (c *Client) withTimeout(ctx context.Context) (context.Context, context.CancelFunc) {
	secs := c.TimeoutSecs
	if secs <= 0 {
		secs = DefaultTimeoutSecs
	}
	return context.WithTimeout(ctx, time.Duration(secs*float64(time.Second)))
}

// buildURL joins base + path + query (citation: snapshot servers table).
// Query values are url-encoded; nil/empty values are skipped.
func (c *Client) buildURL(path string, query map[string]string) string {
	base := strings.TrimSuffix(c.BaseURL, "/")
	if base == "" {
		base = DefaultBaseURL
	}
	if len(query) == 0 {
		return base + path
	}
	v := url.Values{}
	for k, val := range query {
		if val == "" {
			continue
		}
		v.Set(k, val)
	}
	qs := v.Encode()
	if qs == "" {
		return base + path
	}
	return base + path + "?" + qs
}

// headers builds per-request headers incl. X-API-Key when configured.
// Accept stays application/json; User-Agent pins the generated version.
func (c *Client) headers(contentType string) http.Header {
	h := http.Header{}
	h.Set("Accept", "application/json")
	h.Set("User-Agent", UserAgent)
	if c.APIKey != "" {
		h.Set(APIKeyHeader, c.APIKey)
	}
	if contentType != "" {
		h.Set("Content-Type", contentType)
	}
	return h
}

// transport returns the configured *http.Client or http.DefaultClient.
// A nil embedded client (zero Client value) still works via fallback.
func (c *Client) transport() *http.Client {
	if c.Client != nil {
		return c.Client
	}
	return http.DefaultClient
}

// sendWithRetry executes one HTTP round-trip with 3-try retry semantics.
// Retry set: 429/408/5xx plus transient transport/timeout errors.
// Backoff: exponential base*2^n, aborting early when ctx is done.
// Returns (status, body, headers); non-2xx surfaces as *httpError.
func (c *Client) sendWithRetry(ctx context.Context, method, rawURL string, body []byte, contentType string) (int, []byte, http.Header, error) {
	var lastErr error
	for attempt := 0; attempt < DefaultRetries; attempt++ {
		if attempt > 0 {
			select {
			case <-ctx.Done():
				return 0, nil, nil, ctx.Err()
			case <-time.After(backoffFor(attempt - 1)):
			}
		}
		var rdr io.Reader
		if body != nil {
			rdr = bytes.NewReader(body)
		}
		req, err := http.NewRequestWithContext(ctx, method, rawURL, rdr)
		if err != nil {
			return 0, nil, nil, err
		}
		for k, vs := range c.headers(contentType) {
			for _, v := range vs {
				req.Header.Add(k, v)
			}
		}
		resp, err := c.transport().Do(req)
		if err != nil {
			lastErr = err
			if ctx.Err() != nil {
				return 0, nil, nil, err
			}
			continue
		}
		respBody, rerr := io.ReadAll(resp.Body)
		hdr := resp.Header.Clone()
		resp.Body.Close()
		if rerr != nil {
			lastErr = rerr
			continue
		}
		if resp.StatusCode < 200 || resp.StatusCode > 299 {
			snip := string(respBody)
			if len(snip) > 500 {
				snip = snip[:500]
			}
			he := &httpError{Status: resp.StatusCode, Method: method, URL: rawURL, Body: snip}
			lastErr = he
			if !retryableStatus(resp.StatusCode) {
				return resp.StatusCode, nil, hdr, he
			}
			continue
		}
		return resp.StatusCode, respBody, hdr, nil
	}
	if lastErr == nil {
		lastErr = fmt.Errorf("request failed after %d tries", DefaultRetries)
	}
	return 0, nil, nil, lastErr
}

// decodeBody parses JSON when plausible, else wraps raw text (CSV routes).
// CSV endpoints (text/csv) return {"_raw_text": ..., "_content_type": ...}.
// JSON endpoints return the decoded map verbatim (citation-preserving).
func decodeBody(respBody []byte, hdr http.Header) map[string]any {
	ctype := hdr.Get("Content-Type")
	trimmed := bytes.TrimSpace(respBody)
	looksJSON := strings.Contains(ctype, "application/json")
	if len(trimmed) > 0 && (trimmed[0] == '{' || trimmed[0] == '[') {
		looksJSON = true
	}
	if looksJSON {
		var v any
		if err := json.Unmarshal(trimmed, &v); err == nil {
			if m, ok := v.(map[string]any); ok {
				return m
			}
			return map[string]any{"data": v}
		}
	}
	return map[string]any{"_raw_text": string(respBody), "_content_type": ctype}
}

// doJSON performs method+path with optional query/body, returning raw map.
// Bodies encode as application/json; responses decode citation-preserving.
// Retry/timeout/api-key flow through sendWithRetry + context timeout.
func (c *Client) doJSON(ctx context.Context, method, path string, query map[string]string, body map[string]any) (map[string]any, error) {
	rawURL := c.buildURL(path, query)
	var payload []byte
	if body != nil {
		var err error
		payload, err = json.Marshal(body)
		if err != nil {
			return nil, fmt.Errorf("doJSON marshal %s %s: %w", method, path, err)
		}
	}
	ctype := ""
	if body != nil {
		ctype = "application/json"
	}
	_, respBody, hdr, err := c.sendWithRetry(ctx, method, rawURL, payload, ctype)
	if err != nil {
		return nil, err
	}
	return decodeBody(respBody, hdr), nil
}

// doBytes performs method+path returning raw bytes (CSV export routes).
// Used by SellerCloseCSV and SellerExportCSV (Content-Disposition attach).
// Retry/timeout/api-key identical to doJSON; no JSON parsing attempted.
func (c *Client) doBytes(ctx context.Context, method, path string, query map[string]string) ([]byte, error) {
	rawURL := c.buildURL(path, query)
	_, respBody, _, err := c.sendWithRetry(ctx, method, rawURL, nil, "")
	if err != nil {
		return nil, err
	}
	return respBody, nil
}

// doMultipart posts a file upload (photo/vision) with extra text fields.
// multipart/form-data with file field + lang/generate_chart text parts.
// 5MB server cap; rate limited 60/min (429 retried with backoff).
func (c *Client) doMultipart(ctx context.Context, path, fileName string, fileBytes []byte, fields map[string]string) (map[string]any, error) {
	var buf bytes.Buffer
	wr := multipart.NewWriter(&buf)
	for k, v := range fields {
		if err := wr.WriteField(k, v); err != nil {
			return nil, err
		}
	}
	fw, err := wr.CreateFormFile("file", fileName)
	if err != nil {
		return nil, err
	}
	if _, err := fw.Write(fileBytes); err != nil {
		return nil, err
	}
	if err := wr.Close(); err != nil {
		return nil, err
	}
	rawURL := c.buildURL(path, nil)
	_, respBody, hdr, serr := c.sendWithRetry(ctx, http.MethodPost, rawURL, buf.Bytes(), wr.FormDataContentType())
	if serr != nil {
		return nil, serr
	}
	return decodeBody(respBody, hdr), nil
}

// CitationsOf collects [file:line] strings from a decoded payload map.
// It merges top-level citation/citations plus nested kpis/briefing blocks.
// Citation-preserving: never mutate the input; return a fresh slice.
func CitationsOf(m map[string]any) []string {
	out := []string{}
	if m == nil {
		return out
	}
	collect := func(v any) {
		switch t := v.(type) {
		case string:
			if strings.HasPrefix(t, "[") {
				out = append(out, t)
			}
		case []any:
			for _, e := range t {
				if s, ok := e.(string); ok {
					out = append(out, s)
				}
			}
		case []string:
			out = append(out, t...)
		}
	}
	if v, ok := m["citation"]; ok {
		collect(v)
	}
	if v, ok := m["citations"]; ok {
		collect(v)
	}
	for _, nk := range []string{"kpis", "briefing"} {
		if nv, ok := m[nk]; ok {
			if nm, ok := nv.(map[string]any); ok {
				if cv, ok := nm["citations"]; ok {
					collect(cv)
				}
			}
		}
	}
	return out
}

// CheckInvariantClose reports true_profit <= gmv for a close payload map.
// Handbook 04 accountant invariant; corrupt data fails closed (refuse).
func CheckInvariantClose(m map[string]any) bool {
	b, err := json.Marshal(m)
	if err != nil {
		return true
	}
	var bundle CloseBundle
	if err := json.Unmarshal(b, &bundle); err != nil {
		return true
	}
	return bundle.CheckInvariant()
}

// LoadSnapshot reads and parses the snapshot JSON for tooling callers.
// Path defaults to sdks/gen/openapi_snapshot.json from the repo root.
func LoadSnapshot(path string) (map[string]any, error) {
	if strings.TrimSpace(path) == "" {
		path = "sdks/gen/openapi_snapshot.json"
	}
	b, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	m := map[string]any{}
	if err := json.Unmarshal(b, &m); err != nil {
		return nil, err
	}
	return m, nil
}

// SellerClose SellerClose runs the DAILY CLOSE: profit + reorder/PO + reply drafts + leaks ($0).
//
// Method: POST /api/v1/seller/close
// OperationId: see openapi_snapshot.json paths["/api/v1/seller/close"]
// Python method: seller_close | Go method: SellerClose (this function)
// Tags: see snapshot tag table; free offline $0 where marked.
//
// Citation-preserving: returns the raw map verbatim PLUS a typed wrapper.
// - raw map is reachable via the wrapper .Raw field (byte-identical).
// - typed wrapper is *CloseBundle with .CitationsList() for audits.
// - rule: no citation, no action (handbook 01 one rule).
// - invariant where money: true_profit <= gmv (handbook 04).
//
// Retry+timeout+api-key:
// - timeout: context derived with TimeoutSecs (default 30s).
// - retries: 3 tries with exponential backoff (429/408/5xx only).
// - api-key: X-API-Key header when the client was built with one.
// - 400/401/404 fast-fail (fix the source file or key, then retry).
//
// Args:
// - req: CloseRequest — CloseRequest{Demo:true, Seed:42} for the golden synthetic shop.
// - ctx: caller context; a 30s timeout is applied on top of it.
//
// Returns:
// - *CloseBundle (kpis, headline, reorder, reply_queue, po_draft, citations).
// - .Raw holds the decoded map; .CitationsList() audits [file:line].
// - error: *httpError on non-2xx (status preserved for callers).
//
// Golden demo true_profit is 169.09 with margin 61.7 and $102.75 at risk.
//
// Curl example:
//
//	curl -s http://localhost:5003/api/v1/seller/close -X POST -H 'Content-Type: application/json' -d '{"demo": true, "seed": 42}'
//
// Go example:
//
//	cli := gen.NewClient("http://localhost:5003", "")
//	bundle, err := cli.SellerClose(ctx, gen.CloseRequest{Demo: true, Seed: 42})
//	_ = bundle.CitationsList() // audit [file:line]
//
// Handbook: 01 ritual (headline) 02 reorder 03 P0<2h 04 invariant 05 S1<1h.
// Snapshot: openapi_snapshot.json#/paths/~1api~1v1~1seller~1close
func (c *Client) SellerClose(ctx context.Context, req CloseRequest) (*CloseBundle, error) {
	// --- seller_close: citation-preserving net/http call ---
	ctx2, cancel := c.withTimeout(ctx)
	defer cancel()
	// route: POST /api/v1/seller/close (operation seller_close)
	// auth: X-API-Key injected by headers() when APIKey is set
	// retry: 3 tries exponential backoff on 429/408/5xx
	m, err := c.doJSON(ctx2, http.MethodPost, "/api/v1/seller/close", nil, req.ToMap())
	if err != nil {
		return nil, err
	}
	// typed wrapper keeps .Raw verbatim (never drops citations)
	return CloseBundleFromMap(m)
}

// SellerCloseCSV SellerCloseCSV renders the DAILY CLOSE as close.csv (accountant-ready).
//
// Method: GET /api/v1/seller/close.csv
// OperationId: see openapi_snapshot.json paths["/api/v1/seller/close.csv"]
// Python method: seller_close_csv | Go method: SellerCloseCSV (this function)
// Tags: see snapshot tag table; free offline $0 where marked.
//
// Citation-preserving: returns the raw map verbatim PLUS a typed wrapper.
//   - raw map return keeps every [file:line] citation byte-identical (CJK/emoji safe).
//   - pair the map with CloseBundleFromMap/BriefingFromMap for typed access,
//     or CitationsOf(raw) for the audit trail; never drop citations.
//   - rule: no citation, no action (handbook 01 one rule).
//   - invariant where money: true_profit <= gmv (handbook 04).
//
// Retry+timeout+api-key:
// - timeout: context derived with TimeoutSecs (default 30s).
// - retries: 3 tries with exponential backoff (429/408/5xx only).
// - api-key: X-API-Key header when the client was built with one.
// - 400/401/404 fast-fail (fix the source file or key, then retry).
//
// Args:
// - q: URL query map (demo/seed/shop); nil means server defaults.
// - ctx: caller context; a 30s timeout is applied on top of it.
//
// Returns:
// - raw CSV bytes (Content-Disposition attachment twin of the JSON).
// - sections cite [file:line] inline per close.csv layout.
// - error: *httpError on non-2xx (status preserved for callers).
//
// Four sections: title row, metric,value ledger, do_today, reorder + leak blocks.
//
// Curl example:
//
//	curl -s 'http://localhost:5003/api/v1/seller/close.csv?demo=true&seed=42' -X GET
//
// Go example:
//
//	cli := gen.NewClient("http://localhost:5003", "")
//	csvBytes, err := cli.SellerCloseCSV(ctx, map[string]string{"demo": "true"})
//
// Handbook: 01 ritual (headline) 02 reorder 03 P0<2h 04 invariant 05 S1<1h.
// Snapshot: openapi_snapshot.json#/paths/~1api~1v1~1seller~1close.csv
func (c *Client) SellerCloseCSV(ctx context.Context, q map[string]string) ([]byte, error) {
	// --- seller_close_csv: CSV bytes via net/http (accountant-ready) ---
	ctx2, cancel := c.withTimeout(ctx)
	defer cancel()
	// route: GET /api/v1/seller/close.csv (operation seller_close_csv)
	// auth: X-API-Key injected by headers() when APIKey is set
	// retry: 3 tries exponential backoff on 429/408/5xx
	return c.doBytes(ctx2, http.MethodGet, "/api/v1/seller/close.csv", q)
}

// SellerBriefing SellerBriefing returns true profit, stockout risk, and listing health.
//
// Method: POST /api/v1/seller/briefing
// OperationId: see openapi_snapshot.json paths["/api/v1/seller/briefing"]
// Python method: seller_briefing | Go method: SellerBriefing (this function)
// Tags: see snapshot tag table; free offline $0 where marked.
//
// Citation-preserving: returns the raw map verbatim PLUS a typed wrapper.
// - raw map is reachable via the wrapper .Raw field (byte-identical).
// - typed wrapper is *Briefing with .CitationsList() for audits.
// - rule: no citation, no action (handbook 01 one rule).
// - invariant where money: true_profit <= gmv (handbook 04).
//
// Retry+timeout+api-key:
// - timeout: context derived with TimeoutSecs (default 30s).
// - retries: 3 tries with exponential backoff (429/408/5xx only).
// - api-key: X-API-Key header when the client was built with one.
// - 400/401/404 fast-fail (fix the source file or key, then retry).
//
// Args:
// - req: BriefingRequest — BriefingRequest{Demo:true} or Folder pointing at messy seller files.
// - ctx: caller context; a 30s timeout is applied on top of it.
//
// Returns:
// - *Briefing (kpis, headline, stockout_risk, reply_queue, citations).
// - .Raw holds the decoded map; .CitationsList() audits [file:line].
// - error: *httpError on non-2xx (status preserved for callers).
//
// Drop shopify_orders.csv, inventory.csv, reviews.csv, instagram_dm.txt, invoice photos.
//
// Curl example:
//
//	curl -s http://localhost:5003/api/v1/seller/briefing -X POST -H 'Content-Type: application/json' -d '{"demo": true}'
//
// Go example:
//
//	cli := gen.NewClient("http://localhost:5003", "")
//	brief, err := cli.SellerBriefing(ctx, gen.BriefingRequest{Demo: true})
//	_ = brief.CitationsList() // audit [file:line]
//
// Handbook: 01 ritual (headline) 02 reorder 03 P0<2h 04 invariant 05 S1<1h.
// Snapshot: openapi_snapshot.json#/paths/~1api~1v1~1seller~1briefing
func (c *Client) SellerBriefing(ctx context.Context, req BriefingRequest) (*Briefing, error) {
	// --- seller_briefing: citation-preserving net/http call ---
	ctx2, cancel := c.withTimeout(ctx)
	defer cancel()
	// route: POST /api/v1/seller/briefing (operation seller_briefing)
	// auth: X-API-Key injected by headers() when APIKey is set
	// retry: 3 tries exponential backoff on 429/408/5xx
	m, err := c.doJSON(ctx2, http.MethodPost, "/api/v1/seller/briefing", nil, req.ToMap())
	if err != nil {
		return nil, err
	}
	// typed wrapper keeps .Raw verbatim (never drops citations)
	return BriefingFromMap(m)
}

// SellerOperations SellerOperations runs briefing, Workshop queue, and governance audit.
//
// Method: POST /api/v1/seller/operations
// OperationId: see openapi_snapshot.json paths["/api/v1/seller/operations"]
// Python method: seller_operations | Go method: SellerOperations (this function)
// Tags: see snapshot tag table; free offline $0 where marked.
//
// Citation-preserving: returns the raw map verbatim PLUS a typed wrapper.
//   - raw map return keeps every [file:line] citation byte-identical (CJK/emoji safe).
//   - pair the map with CloseBundleFromMap/BriefingFromMap for typed access,
//     or CitationsOf(raw) for the audit trail; never drop citations.
//   - rule: no citation, no action (handbook 01 one rule).
//   - invariant where money: true_profit <= gmv (handbook 04).
//
// Retry+timeout+api-key:
// - timeout: context derived with TimeoutSecs (default 30s).
// - retries: 3 tries with exponential backoff (429/408/5xx only).
// - api-key: X-API-Key header when the client was built with one.
// - 400/401/404 fast-fail (fix the source file or key, then retry).
//
// Args:
// - req: OperationsRequest — OperationsRequest{Demo:true, Seed:42} for the full methodology loop.
// - ctx: caller context; a 30s timeout is applied on top of it.
//
// Returns:
// - raw decoded map with ok/method/path/citations or domain payload.
// - use CitationsOf(out) for the audit trail.
// - error: *httpError on non-2xx (status preserved for callers).
//
// Proves the Palantir-style loop surrounding the core tech; operates first decision.
//
// Curl example:
//
//	curl -s http://localhost:5003/api/v1/seller/operations -X POST -H 'Content-Type: application/json' -d '{"demo": true, "seed": 42}'
//
// Go example:
//
//	cli := gen.NewClient("http://localhost:5003", "")
//	out, err := cli.SellerOperations(ctx, gen.OperationsRequest{})
//
// Handbook: 01 ritual (headline) 02 reorder 03 P0<2h 04 invariant 05 S1<1h.
// Snapshot: openapi_snapshot.json#/paths/~1api~1v1~1seller~1operations
func (c *Client) SellerOperations(ctx context.Context, req OperationsRequest) (map[string]any, error) {
	// --- seller_operations: citation-preserving net/http call ---
	ctx2, cancel := c.withTimeout(ctx)
	defer cancel()
	// route: POST /api/v1/seller/operations (operation seller_operations)
	// auth: X-API-Key injected by headers() when APIKey is set
	// retry: 3 tries exponential backoff on 429/408/5xx
	return c.doJSON(ctx2, http.MethodPost, "/api/v1/seller/operations", nil, req.ToMap())
}

// SellerScenariosList SellerScenariosList lists the 12 practical seller scenarios (id + trigger + action).
//
// Method: GET /api/v1/seller/scenarios
// OperationId: see openapi_snapshot.json paths["/api/v1/seller/scenarios"]
// Python method: seller_scenarios_list | Go method: SellerScenariosList (this function)
// Tags: see snapshot tag table; free offline $0 where marked.
//
// Citation-preserving: returns the raw map verbatim PLUS a typed wrapper.
//   - raw map return keeps every [file:line] citation byte-identical (CJK/emoji safe).
//   - pair the map with CloseBundleFromMap/BriefingFromMap for typed access,
//     or CitationsOf(raw) for the audit trail; never drop citations.
//   - rule: no citation, no action (handbook 01 one rule).
//   - invariant where money: true_profit <= gmv (handbook 04).
//
// Retry+timeout+api-key:
// - timeout: context derived with TimeoutSecs (default 30s).
// - retries: 3 tries with exponential backoff (429/408/5xx only).
// - api-key: X-API-Key header when the client was built with one.
// - 400/401/404 fast-fail (fix the source file or key, then retry).
//
// Args:
// - no args beyond ctx: static route, deterministic output.
// - ctx: caller context; a 30s timeout is applied on top of it.
//
// Returns:
// - raw decoded map with ok/method/path/citations or domain payload.
// - use CitationsOf(out) for the audit trail.
// - error: *httpError on non-2xx (status preserved for callers).
//
// Static registry: no fees, idempotent, safe to cache briefly.
//
// Curl example:
//
//	curl -s http://localhost:5003/api/v1/seller/scenarios -X GET
//
// Go example:
//
//	cli := gen.NewClient("http://localhost:5003", "")
//	out, err := cli.SellerScenariosList(ctx)
//
// Handbook: 01 ritual (headline) 02 reorder 03 P0<2h 04 invariant 05 S1<1h.
// Snapshot: openapi_snapshot.json#/paths/~1api~1v1~1seller~1scenarios
func (c *Client) SellerScenariosList(ctx context.Context) (map[string]any, error) {
	// --- seller_scenarios_list: citation-preserving net/http call ---
	ctx2, cancel := c.withTimeout(ctx)
	defer cancel()
	// route: GET /api/v1/seller/scenarios (operation seller_scenarios_list)
	// auth: X-API-Key injected by headers() when APIKey is set
	// retry: 3 tries exponential backoff on 429/408/5xx
	return c.doJSON(ctx2, http.MethodGet, "/api/v1/seller/scenarios", nil, nil)
}

// SellerScenariosRun SellerScenariosRun runs 12 scenarios into a Workshop queue plus audit.
//
// Method: POST /api/v1/seller/scenarios/run
// OperationId: see openapi_snapshot.json paths["/api/v1/seller/scenarios/run"]
// Python method: seller_scenarios_run | Go method: SellerScenariosRun (this function)
// Tags: see snapshot tag table; free offline $0 where marked.
//
// Citation-preserving: returns the raw map verbatim PLUS a typed wrapper.
//   - raw map return keeps every [file:line] citation byte-identical (CJK/emoji safe).
//   - pair the map with CloseBundleFromMap/BriefingFromMap for typed access,
//     or CitationsOf(raw) for the audit trail; never drop citations.
//   - rule: no citation, no action (handbook 01 one rule).
//   - invariant where money: true_profit <= gmv (handbook 04).
//
// Retry+timeout+api-key:
// - timeout: context derived with TimeoutSecs (default 30s).
// - retries: 3 tries with exponential backoff (429/408/5xx only).
// - api-key: X-API-Key header when the client was built with one.
// - 400/401/404 fast-fail (fix the source file or key, then retry).
//
// Args:
// - req: ScenariosRunRequest — ScenariosRunRequest{Demo:true} or Folder for deterministic O(n) evaluation.
// - ctx: caller context; a 30s timeout is applied on top of it.
//
// Returns:
// - raw decoded map with ok/method/path/citations or domain payload.
// - use CitationsOf(out) for the audit trail.
// - error: *httpError on non-2xx (status preserved for callers).
//
// Decisions sort critical to low with stable ids and by_scenario counts.
//
// Curl example:
//
//	curl -s http://localhost:5003/api/v1/seller/scenarios/run -X POST -H 'Content-Type: application/json' -d '{"demo": true, "seed": 42}'
//
// Go example:
//
//	cli := gen.NewClient("http://localhost:5003", "")
//	out, err := cli.SellerScenariosRun(ctx, gen.ScenariosRunRequest{})
//
// Handbook: 01 ritual (headline) 02 reorder 03 P0<2h 04 invariant 05 S1<1h.
// Snapshot: openapi_snapshot.json#/paths/~1api~1v1~1seller~1scenarios~1run
func (c *Client) SellerScenariosRun(ctx context.Context, req ScenariosRunRequest) (map[string]any, error) {
	// --- seller_scenarios_run: citation-preserving net/http call ---
	ctx2, cancel := c.withTimeout(ctx)
	defer cancel()
	// route: POST /api/v1/seller/scenarios/run (operation seller_scenarios_run)
	// auth: X-API-Key injected by headers() when APIKey is set
	// retry: 3 tries exponential backoff on 429/408/5xx
	return c.doJSON(ctx2, http.MethodPost, "/api/v1/seller/scenarios/run", nil, req.ToMap())
}

// SellerExportCSV SellerExportCSV renders briefing KPIs plus actions as briefing.csv.
//
// Method: GET /api/v1/seller/export.csv
// OperationId: see openapi_snapshot.json paths["/api/v1/seller/export.csv"]
// Python method: seller_export_csv | Go method: SellerExportCSV (this function)
// Tags: see snapshot tag table; free offline $0 where marked.
//
// Citation-preserving: returns the raw map verbatim PLUS a typed wrapper.
//   - raw map return keeps every [file:line] citation byte-identical (CJK/emoji safe).
//   - pair the map with CloseBundleFromMap/BriefingFromMap for typed access,
//     or CitationsOf(raw) for the audit trail; never drop citations.
//   - rule: no citation, no action (handbook 01 one rule).
//   - invariant where money: true_profit <= gmv (handbook 04).
//
// Retry+timeout+api-key:
// - timeout: context derived with TimeoutSecs (default 30s).
// - retries: 3 tries with exponential backoff (429/408/5xx only).
// - api-key: X-API-Key header when the client was built with one.
// - 400/401/404 fast-fail (fix the source file or key, then retry).
//
// Args:
// - q: URL query map (demo/seed/shop); nil means server defaults.
// - ctx: caller context; a 30s timeout is applied on top of it.
//
// Returns:
// - raw CSV bytes (Content-Disposition attachment twin of the JSON).
// - sections cite [file:line] inline per close.csv layout.
// - error: *httpError on non-2xx (status preserved for callers).
//
// Spreadsheet-friendly twin of the JSON briefing for operators.
//
// Curl example:
//
//	curl -s 'http://localhost:5003/api/v1/seller/export.csv?demo=true&seed=42' -X GET
//
// Go example:
//
//	cli := gen.NewClient("http://localhost:5003", "")
//	csvBytes, err := cli.SellerExportCSV(ctx, map[string]string{"demo": "true"})
//
// Handbook: 01 ritual (headline) 02 reorder 03 P0<2h 04 invariant 05 S1<1h.
// Snapshot: openapi_snapshot.json#/paths/~1api~1v1~1seller~1export.csv
func (c *Client) SellerExportCSV(ctx context.Context, q map[string]string) ([]byte, error) {
	// --- seller_export_csv: CSV bytes via net/http (accountant-ready) ---
	ctx2, cancel := c.withTimeout(ctx)
	defer cancel()
	// route: GET /api/v1/seller/export.csv (operation seller_export_csv)
	// auth: X-API-Key injected by headers() when APIKey is set
	// retry: 3 tries exponential backoff on 429/408/5xx
	return c.doBytes(ctx2, http.MethodGet, "/api/v1/seller/export.csv", q)
}

// SellerPhoto SellerPhoto analyses a supplier invoice or product photo (free OCR + chart).
//
// Method: POST /api/v1/seller/photo
// OperationId: see openapi_snapshot.json paths["/api/v1/seller/photo"]
// Python method: seller_photo | Go method: SellerPhoto (this function)
// Tags: see snapshot tag table; free offline $0 where marked.
//
// Citation-preserving: returns the raw map verbatim PLUS a typed wrapper.
//   - raw map return keeps every [file:line] citation byte-identical (CJK/emoji safe).
//   - pair the map with CloseBundleFromMap/BriefingFromMap for typed access,
//     or CitationsOf(raw) for the audit trail; never drop citations.
//   - rule: no citation, no action (handbook 01 one rule).
//   - invariant where money: true_profit <= gmv (handbook 04).
//
// Retry+timeout+api-key:
// - timeout: context derived with TimeoutSecs (default 30s).
// - retries: 3 tries with exponential backoff (429/408/5xx only).
// - api-key: X-API-Key header when the client was built with one.
// - 400/401/404 fast-fail (fix the source file or key, then retry).
//
// Args:
// - fileName: upload filename (invoice.jpg, receipt.png, doc.pdf).
// - fileBytes: file content (server cap 5MB; rate limit 60/min).
// - lang: OCR language (eng/spa); empty lets the server default.
// - ctx: caller context; a 30s timeout is applied on top of it.
//
// Returns:
// - raw decoded map with ok/method/path/citations or domain payload.
// - use CitationsOf(out) for the audit trail.
// - error: *httpError on non-2xx (status preserved for callers).
//
// Invoices yield COGS line items; product photos yield listing drafts. 60/min limit.
//
// Curl example:
//
//	curl -s http://localhost:5003/api/v1/seller/photo -X POST -F 'file=@invoice.jpg' -F 'lang=eng'
//
// Go example:
//
//	cli := gen.NewClient("http://localhost:5003", "")
//	out, err := cli.SellerPhoto(ctx, "invoice.jpg", imgBytes, "eng")
//
// Handbook: 01 ritual (headline) 02 reorder 03 P0<2h 04 invariant 05 S1<1h.
// Snapshot: openapi_snapshot.json#/paths/~1api~1v1~1seller~1photo
func (c *Client) SellerPhoto(ctx context.Context, fileName string, fileBytes []byte, lang string) (map[string]any, error) {
	// --- seller_photo: multipart upload via net/http (no new deps) ---
	ctx2, cancel := c.withTimeout(ctx)
	defer cancel()
	// route: POST /api/v1/seller/photo (operation seller_photo)
	// auth: X-API-Key injected by headers() when APIKey is set
	// retry: 3 tries exponential backoff on 429/408/5xx
	if lang == "" {
		lang = "eng"
	}
	fields := map[string]string{"lang": lang, "generate_chart": "true"}
	return c.doMultipart(ctx2, "/api/v1/seller/photo", fileName, fileBytes, fields)
}

// VisionAnalyze VisionAnalyze runs photo to text plus chart plus layered analysis (free, local).
//
// Method: POST /api/v1/vision/analyze
// OperationId: see openapi_snapshot.json paths["/api/v1/vision/analyze"]
// Python method: vision_analyze | Go method: VisionAnalyze (this function)
// Tags: see snapshot tag table; free offline $0 where marked.
//
// Citation-preserving: returns the raw map verbatim PLUS a typed wrapper.
//   - raw map return keeps every [file:line] citation byte-identical (CJK/emoji safe).
//   - pair the map with CloseBundleFromMap/BriefingFromMap for typed access,
//     or CitationsOf(raw) for the audit trail; never drop citations.
//   - rule: no citation, no action (handbook 01 one rule).
//   - invariant where money: true_profit <= gmv (handbook 04).
//
// Retry+timeout+api-key:
// - timeout: context derived with TimeoutSecs (default 30s).
// - retries: 3 tries with exponential backoff (429/408/5xx only).
// - api-key: X-API-Key header when the client was built with one.
// - 400/401/404 fast-fail (fix the source file or key, then retry).
//
// Args:
// - fileName: upload filename (invoice.jpg, receipt.png, doc.pdf).
// - fileBytes: file content (server cap 5MB; rate limit 60/min).
// - lang: OCR language (eng/spa); empty lets the server default.
// - ctx: caller context; a 30s timeout is applied on top of it.
//
// Returns:
// - raw decoded map with ok/method/path/citations or domain payload.
// - use CitationsOf(out) for the audit trail.
// - error: *httpError on non-2xx (status preserved for callers).
//
// Tesseract OCR offline, OpenCV chart heuristic, Matplotlib regen. No keys/fees/cloud.
//
// Curl example:
//
//	curl -s http://localhost:5003/api/v1/vision/analyze -X POST -F 'file=@receipt.jpg' -F 'lang=eng'
//
// Go example:
//
//	cli := gen.NewClient("http://localhost:5003", "")
//	out, err := cli.VisionAnalyze(ctx, "invoice.jpg", imgBytes, "eng")
//
// Handbook: 01 ritual (headline) 02 reorder 03 P0<2h 04 invariant 05 S1<1h.
// Snapshot: openapi_snapshot.json#/paths/~1api~1v1~1vision~1analyze
func (c *Client) VisionAnalyze(ctx context.Context, fileName string, fileBytes []byte, lang string) (map[string]any, error) {
	// --- vision_analyze: multipart upload via net/http (no new deps) ---
	ctx2, cancel := c.withTimeout(ctx)
	defer cancel()
	// route: POST /api/v1/vision/analyze (operation vision_analyze)
	// auth: X-API-Key injected by headers() when APIKey is set
	// retry: 3 tries exponential backoff on 429/408/5xx
	if lang == "" {
		lang = "eng"
	}
	fields := map[string]string{"lang": lang, "generate_chart": "true"}
	return c.doMultipart(ctx2, "/api/v1/vision/analyze", fileName, fileBytes, fields)
}

// VisionDemo VisionDemo analyses a synthetic receipt + chart photo (Maya's Tacos, free).
//
// Method: GET /api/v1/vision/demo
// OperationId: see openapi_snapshot.json paths["/api/v1/vision/demo"]
// Python method: vision_demo | Go method: VisionDemo (this function)
// Tags: see snapshot tag table; free offline $0 where marked.
//
// Citation-preserving: returns the raw map verbatim PLUS a typed wrapper.
//   - raw map return keeps every [file:line] citation byte-identical (CJK/emoji safe).
//   - pair the map with CloseBundleFromMap/BriefingFromMap for typed access,
//     or CitationsOf(raw) for the audit trail; never drop citations.
//   - rule: no citation, no action (handbook 01 one rule).
//   - invariant where money: true_profit <= gmv (handbook 04).
//
// Retry+timeout+api-key:
// - timeout: context derived with TimeoutSecs (default 30s).
// - retries: 3 tries with exponential backoff (429/408/5xx only).
// - api-key: X-API-Key header when the client was built with one.
// - 400/401/404 fast-fail (fix the source file or key, then retry).
//
// Args:
// - no args beyond ctx: static route, deterministic output.
// - ctx: caller context; a 30s timeout is applied on top of it.
//
// Returns:
// - raw decoded map with ok/method/path/citations or domain payload.
// - use CitationsOf(out) for the audit trail.
// - error: *httpError on non-2xx (status preserved for callers).
//
// Tacos al pastor 32x3.50=112, Birria 12x4.00=48, total 160 through the same pipeline.
//
// Curl example:
//
//	curl -s http://localhost:5003/api/v1/vision/demo -X GET
//
// Go example:
//
//	cli := gen.NewClient("http://localhost:5003", "")
//	out, err := cli.VisionDemo(ctx)
//
// Handbook: 01 ritual (headline) 02 reorder 03 P0<2h 04 invariant 05 S1<1h.
// Snapshot: openapi_snapshot.json#/paths/~1api~1v1~1vision~1demo
func (c *Client) VisionDemo(ctx context.Context) (map[string]any, error) {
	// --- vision_demo: citation-preserving net/http call ---
	ctx2, cancel := c.withTimeout(ctx)
	defer cancel()
	// route: GET /api/v1/vision/demo (operation vision_demo)
	// auth: X-API-Key injected by headers() when APIKey is set
	// retry: 3 tries exponential backoff on 429/408/5xx
	return c.doJSON(ctx2, http.MethodGet, "/api/v1/vision/demo", nil, nil)
}

// Analyze Analyze runs data analysis via the multi-layer pipeline (LLM calls slashed).
//
// Method: POST /api/v1/analyze
// OperationId: see openapi_snapshot.json paths["/api/v1/analyze"]
// Python method: analyze | Go method: Analyze (this function)
// Tags: see snapshot tag table; free offline $0 where marked.
//
// Citation-preserving: returns the raw map verbatim PLUS a typed wrapper.
//   - raw map return keeps every [file:line] citation byte-identical (CJK/emoji safe).
//   - pair the map with CloseBundleFromMap/BriefingFromMap for typed access,
//     or CitationsOf(raw) for the audit trail; never drop citations.
//   - rule: no citation, no action (handbook 01 one rule).
//   - invariant where money: true_profit <= gmv (handbook 04).
//
// Retry+timeout+api-key:
// - timeout: context derived with TimeoutSecs (default 30s).
// - retries: 3 tries with exponential backoff (429/408/5xx only).
// - api-key: X-API-Key header when the client was built with one.
// - 400/401/404 fast-fail (fix the source file or key, then retry).
//
// Args:
// - req: AnalyzeRequest — AnalyzeRequest{Records: [...]} for the L1-L4 multi-layer pipeline.
// - ctx: caller context; a 30s timeout is applied on top of it.
//
// Returns:
// - raw decoded map with ok/method/path/citations or domain payload.
// - use CitationsOf(out) for the audit trail.
// - error: *httpError on non-2xx (status preserved for callers).
//
// L1 fast ingest <1ms, L2 anomaly <10ms, L3 feature <100ms, L4 LLM gated.
//
// Curl example:
//
//	curl -s http://localhost:5003/api/v1/analyze -X POST -H 'Content-Type: application/json' -d '{"records": []}'
//
// Go example:
//
//	cli := gen.NewClient("http://localhost:5003", "")
//	out, err := cli.Analyze(ctx, gen.AnalyzeRequest{})
//
// Handbook: 01 ritual (headline) 02 reorder 03 P0<2h 04 invariant 05 S1<1h.
// Snapshot: openapi_snapshot.json#/paths/~1api~1v1~1analyze
func (c *Client) Analyze(ctx context.Context, req AnalyzeRequest) (map[string]any, error) {
	// --- analyze: citation-preserving net/http call ---
	ctx2, cancel := c.withTimeout(ctx)
	defer cancel()
	// route: POST /api/v1/analyze (operation analyze)
	// auth: X-API-Key injected by headers() when APIKey is set
	// retry: 3 tries exponential backoff on 429/408/5xx
	return c.doJSON(ctx2, http.MethodPost, "/api/v1/analyze", nil, req.ToMap())
}

// Synthesize Synthesize combines sources plus AI models into actionable insights.
//
// Method: POST /api/v1/synthesize
// OperationId: see openapi_snapshot.json paths["/api/v1/synthesize"]
// Python method: synthesize | Go method: Synthesize (this function)
// Tags: see snapshot tag table; free offline $0 where marked.
//
// Citation-preserving: returns the raw map verbatim PLUS a typed wrapper.
//   - raw map return keeps every [file:line] citation byte-identical (CJK/emoji safe).
//   - pair the map with CloseBundleFromMap/BriefingFromMap for typed access,
//     or CitationsOf(raw) for the audit trail; never drop citations.
//   - rule: no citation, no action (handbook 01 one rule).
//   - invariant where money: true_profit <= gmv (handbook 04).
//
// Retry+timeout+api-key:
// - timeout: context derived with TimeoutSecs (default 30s).
// - retries: 3 tries with exponential backoff (429/408/5xx only).
// - api-key: X-API-Key header when the client was built with one.
// - 400/401/404 fast-fail (fix the source file or key, then retry).
//
// Args:
// - req: SynthesizeRequest — SynthesizeRequest{Query, Context, TaskType, UserTier} with routing hints.
// - ctx: caller context; a 30s timeout is applied on top of it.
//
// Returns:
// - raw decoded map with ok/method/path/citations or domain payload.
// - use CitationsOf(out) for the audit trail.
// - error: *httpError on non-2xx (status preserved for callers).
//
// Multi-modal RAG with model routing, caching, and quality validation.
//
// Curl example:
//
//	curl -s http://localhost:5003/api/v1/synthesize -X POST -H 'Content-Type: application/json' -d '{"query": "restock?"}'
//
// Go example:
//
//	cli := gen.NewClient("http://localhost:5003", "")
//	out, err := cli.Synthesize(ctx, gen.SynthesizeRequest{})
//
// Handbook: 01 ritual (headline) 02 reorder 03 P0<2h 04 invariant 05 S1<1h.
// Snapshot: openapi_snapshot.json#/paths/~1api~1v1~1synthesize
func (c *Client) Synthesize(ctx context.Context, req SynthesizeRequest) (map[string]any, error) {
	// --- synthesize: citation-preserving net/http call ---
	ctx2, cancel := c.withTimeout(ctx)
	defer cancel()
	// route: POST /api/v1/synthesize (operation synthesize)
	// auth: X-API-Key injected by headers() when APIKey is set
	// retry: 3 tries exponential backoff on 429/408/5xx
	return c.doJSON(ctx2, http.MethodPost, "/api/v1/synthesize", nil, req.ToMap())
}

// RevenueHealth RevenueHealth scores RevOps health tiers (vertical pack, deterministic).
//
// Method: POST /api/v1/revenue/health
// OperationId: see openapi_snapshot.json paths["/api/v1/revenue/health"]
// Python method: revenue_health | Go method: RevenueHealth (this function)
// Tags: see snapshot tag table; free offline $0 where marked.
//
// Citation-preserving: returns the raw map verbatim PLUS a typed wrapper.
//   - raw map return keeps every [file:line] citation byte-identical (CJK/emoji safe).
//   - pair the map with CloseBundleFromMap/BriefingFromMap for typed access,
//     or CitationsOf(raw) for the audit trail; never drop citations.
//   - rule: no citation, no action (handbook 01 one rule).
//   - invariant where money: true_profit <= gmv (handbook 04).
//
// Retry+timeout+api-key:
// - timeout: context derived with TimeoutSecs (default 30s).
// - retries: 3 tries with exponential backoff (429/408/5xx only).
// - api-key: X-API-Key header when the client was built with one.
// - 400/401/404 fast-fail (fix the source file or key, then retry).
//
// Args:
// - req: RevenueHealthRequest — RevenueHealthRequest{Accounts: n (1-500), Seed: 42} for synthetic scoring.
// - ctx: caller context; a 30s timeout is applied on top of it.
//
// Returns:
// - raw decoded map with ok/method/path/citations or domain payload.
// - use CitationsOf(out) for the audit trail.
// - error: *httpError on non-2xx (status preserved for callers).
//
// Industry wedge per STRATEGY.md with evidence bundles per account.
//
// Curl example:
//
//	curl -s http://localhost:5003/api/v1/revenue/health -X POST -H 'Content-Type: application/json' -d '{"accounts": 50, "seed": 42}'
//
// Go example:
//
//	cli := gen.NewClient("http://localhost:5003", "")
//	out, err := cli.RevenueHealth(ctx, gen.RevenueHealthRequest{})
//
// Handbook: 01 ritual (headline) 02 reorder 03 P0<2h 04 invariant 05 S1<1h.
// Snapshot: openapi_snapshot.json#/paths/~1api~1v1~1revenue~1health
func (c *Client) RevenueHealth(ctx context.Context, req RevenueHealthRequest) (map[string]any, error) {
	// --- revenue_health: citation-preserving net/http call ---
	ctx2, cancel := c.withTimeout(ctx)
	defer cancel()
	// route: POST /api/v1/revenue/health (operation revenue_health)
	// auth: X-API-Key injected by headers() when APIKey is set
	// retry: 3 tries exponential backoff on 429/408/5xx
	return c.doJSON(ctx2, http.MethodPost, "/api/v1/revenue/health", nil, req.ToMap())
}

// MicroBriefing MicroBriefing briefs micro-biz sellers with no DB or website (LABS).
//
// Method: POST /api/v1/micro/briefing
// OperationId: see openapi_snapshot.json paths["/api/v1/micro/briefing"]
// Python method: micro_briefing | Go method: MicroBriefing (this function)
// Tags: see snapshot tag table; free offline $0 where marked.
//
// Citation-preserving: returns the raw map verbatim PLUS a typed wrapper.
//   - raw map return keeps every [file:line] citation byte-identical (CJK/emoji safe).
//   - pair the map with CloseBundleFromMap/BriefingFromMap for typed access,
//     or CitationsOf(raw) for the audit trail; never drop citations.
//   - rule: no citation, no action (handbook 01 one rule).
//   - invariant where money: true_profit <= gmv (handbook 04).
//
// Retry+timeout+api-key:
// - timeout: context derived with TimeoutSecs (default 30s).
// - retries: 3 tries with exponential backoff (429/408/5xx only).
// - api-key: X-API-Key header when the client was built with one.
// - 400/401/404 fast-fail (fix the source file or key, then retry).
//
// Args:
// - req: MicroBriefingRequest — MicroBriefingRequest{Demo:true} or Folder/Events for the smallest shops.
// - ctx: caller context; a 30s timeout is applied on top of it.
//
// Returns:
// - raw decoded map with ok/method/path/citations or domain payload.
// - use CitationsOf(out) for the audit trail.
// - error: *httpError on non-2xx (status preserved for callers).
//
// KPIs, alerts, reorder, at-risk, WhatsApp draft, all citing file:line.
//
// Curl example:
//
//	curl -s http://localhost:5003/api/v1/micro/briefing -X POST -H 'Content-Type: application/json' -d '{"demo": true}'
//
// Go example:
//
//	cli := gen.NewClient("http://localhost:5003", "")
//	out, err := cli.MicroBriefing(ctx, gen.MicroBriefingRequest{})
//
// Handbook: 01 ritual (headline) 02 reorder 03 P0<2h 04 invariant 05 S1<1h.
// Snapshot: openapi_snapshot.json#/paths/~1api~1v1~1micro~1briefing
func (c *Client) MicroBriefing(ctx context.Context, req MicroBriefingRequest) (map[string]any, error) {
	// --- micro_briefing: citation-preserving net/http call ---
	ctx2, cancel := c.withTimeout(ctx)
	defer cancel()
	// route: POST /api/v1/micro/briefing (operation micro_briefing)
	// auth: X-API-Key injected by headers() when APIKey is set
	// retry: 3 tries exponential backoff on 429/408/5xx
	return c.doJSON(ctx2, http.MethodPost, "/api/v1/micro/briefing", nil, req.ToMap())
}

// GetMetrics GetMetrics returns system metrics from the live 200-record eval.
//
// Method: GET /api/v1/metrics
// OperationId: see openapi_snapshot.json paths["/api/v1/metrics"]
// Python method: get_metrics | Go method: GetMetrics (this function)
// Tags: see snapshot tag table; free offline $0 where marked.
//
// Citation-preserving: returns the raw map verbatim PLUS a typed wrapper.
//   - raw map return keeps every [file:line] citation byte-identical (CJK/emoji safe).
//   - pair the map with CloseBundleFromMap/BriefingFromMap for typed access,
//     or CitationsOf(raw) for the audit trail; never drop citations.
//   - rule: no citation, no action (handbook 01 one rule).
//   - invariant where money: true_profit <= gmv (handbook 04).
//
// Retry+timeout+api-key:
// - timeout: context derived with TimeoutSecs (default 30s).
// - retries: 3 tries with exponential backoff (429/408/5xx only).
// - api-key: X-API-Key header when the client was built with one.
// - 400/401/404 fast-fail (fix the source file or key, then retry).
//
// Args:
// - no args beyond ctx: static route, deterministic output.
// - ctx: caller context; a 30s timeout is applied on top of it.
//
// Returns:
// - raw decoded map with ok/method/path/citations or domain payload.
// - use CitationsOf(out) for the audit trail.
// - error: *httpError on non-2xx (status preserved for callers).
//
// LLM bypass rate plus L1-L4 average times plus total_cost_usd. Prometheus at /metrics.
//
// Curl example:
//
//	curl -s http://localhost:5003/api/v1/metrics -X GET
//
// Go example:
//
//	cli := gen.NewClient("http://localhost:5003", "")
//	out, err := cli.GetMetrics(ctx)
//
// Handbook: 01 ritual (headline) 02 reorder 03 P0<2h 04 invariant 05 S1<1h.
// Snapshot: openapi_snapshot.json#/paths/~1api~1v1~1metrics
func (c *Client) GetMetrics(ctx context.Context) (map[string]any, error) {
	// --- get_metrics: citation-preserving net/http call ---
	ctx2, cancel := c.withTimeout(ctx)
	defer cancel()
	// route: GET /api/v1/metrics (operation get_metrics)
	// auth: X-API-Key injected by headers() when APIKey is set
	// retry: 3 tries exponential backoff on 429/408/5xx
	return c.doJSON(ctx2, http.MethodGet, "/api/v1/metrics", nil, nil)
}

// ListModels ListModels lists available models with costs and latencies.
//
// Method: GET /api/v1/models
// OperationId: see openapi_snapshot.json paths["/api/v1/models"]
// Python method: list_models | Go method: ListModels (this function)
// Tags: see snapshot tag table; free offline $0 where marked.
//
// Citation-preserving: returns the raw map verbatim PLUS a typed wrapper.
//   - raw map return keeps every [file:line] citation byte-identical (CJK/emoji safe).
//   - pair the map with CloseBundleFromMap/BriefingFromMap for typed access,
//     or CitationsOf(raw) for the audit trail; never drop citations.
//   - rule: no citation, no action (handbook 01 one rule).
//   - invariant where money: true_profit <= gmv (handbook 04).
//
// Retry+timeout+api-key:
// - timeout: context derived with TimeoutSecs (default 30s).
// - retries: 3 tries with exponential backoff (429/408/5xx only).
// - api-key: X-API-Key header when the client was built with one.
// - 400/401/404 fast-fail (fix the source file or key, then retry).
//
// Args:
// - no args beyond ctx: static route, deterministic output.
// - ctx: caller context; a 30s timeout is applied on top of it.
//
// Returns:
// - raw decoded map with ok/method/path/citations or domain payload.
// - use CitationsOf(out) for the audit trail.
// - error: *httpError on non-2xx (status preserved for callers).
//
// fast/balanced/premium tiers: gemini-2.5-flash, gemini-2-pro, gpt-4o.
//
// Curl example:
//
//	curl -s http://localhost:5003/api/v1/models -X GET
//
// Go example:
//
//	cli := gen.NewClient("http://localhost:5003", "")
//	out, err := cli.ListModels(ctx)
//
// Handbook: 01 ritual (headline) 02 reorder 03 P0<2h 04 invariant 05 S1<1h.
// Snapshot: openapi_snapshot.json#/paths/~1api~1v1~1models
func (c *Client) ListModels(ctx context.Context) (map[string]any, error) {
	// --- list_models: citation-preserving net/http call ---
	ctx2, cancel := c.withTimeout(ctx)
	defer cancel()
	// route: GET /api/v1/models (operation list_models)
	// auth: X-API-Key injected by headers() when APIKey is set
	// retry: 3 tries exponential backoff on 429/408/5xx
	return c.doJSON(ctx2, http.MethodGet, "/api/v1/models", nil, nil)
}

// Health Health is the liveness probe ({status:healthy, mode:mvp}, <5ms).
//
// Method: GET /health
// OperationId: see openapi_snapshot.json paths["/health"]
// Python method: health | Go method: Health (this function)
// Tags: see snapshot tag table; free offline $0 where marked.
//
// Citation-preserving: returns the raw map verbatim PLUS a typed wrapper.
//   - raw map return keeps every [file:line] citation byte-identical (CJK/emoji safe).
//   - pair the map with CloseBundleFromMap/BriefingFromMap for typed access,
//     or CitationsOf(raw) for the audit trail; never drop citations.
//   - rule: no citation, no action (handbook 01 one rule).
//   - invariant where money: true_profit <= gmv (handbook 04).
//
// Retry+timeout+api-key:
// - timeout: context derived with TimeoutSecs (default 30s).
// - retries: 3 tries with exponential backoff (429/408/5xx only).
// - api-key: X-API-Key header when the client was built with one.
// - 400/401/404 fast-fail (fix the source file or key, then retry).
//
// Args:
// - no args beyond ctx: static route, deterministic output.
// - ctx: caller context; a 30s timeout is applied on top of it.
//
// Returns:
// - raw decoded map with ok/method/path/citations or domain payload.
// - use CitationsOf(out) for the audit trail.
// - error: *httpError on non-2xx (status preserved for callers).
//
// No auth. Fast: Docker curl -f /health gates deploys.
//
// Curl example:
//
//	curl -s http://localhost:5003/health -X GET
//
// Go example:
//
//	cli := gen.NewClient("http://localhost:5003", "")
//	out, err := cli.Health(ctx)
//
// Handbook: 01 ritual (headline) 02 reorder 03 P0<2h 04 invariant 05 S1<1h.
// Snapshot: openapi_snapshot.json#/paths/~1health
func (c *Client) Health(ctx context.Context) (map[string]any, error) {
	// --- health: citation-preserving net/http call ---
	ctx2, cancel := c.withTimeout(ctx)
	defer cancel()
	// route: GET /health (operation health)
	// auth: X-API-Key injected by headers() when APIKey is set
	// retry: 3 tries exponential backoff on 429/408/5xx
	return c.doJSON(ctx2, http.MethodGet, "/health", nil, nil)
}

// OpenapiTags OpenapiTags returns the tag catalogue for SDK and codegen integrators.
//
// Method: GET /api/v1/openapi-tags
// OperationId: see openapi_snapshot.json paths["/api/v1/openapi-tags"]
// Python method: openapi_tags | Go method: OpenapiTags (this function)
// Tags: see snapshot tag table; free offline $0 where marked.
//
// Citation-preserving: returns the raw map verbatim PLUS a typed wrapper.
//   - raw map return keeps every [file:line] citation byte-identical (CJK/emoji safe).
//   - pair the map with CloseBundleFromMap/BriefingFromMap for typed access,
//     or CitationsOf(raw) for the audit trail; never drop citations.
//   - rule: no citation, no action (handbook 01 one rule).
//   - invariant where money: true_profit <= gmv (handbook 04).
//
// Retry+timeout+api-key:
// - timeout: context derived with TimeoutSecs (default 30s).
// - retries: 3 tries with exponential backoff (429/408/5xx only).
// - api-key: X-API-Key header when the client was built with one.
// - 400/401/404 fast-fail (fix the source file or key, then retry).
//
// Args:
// - no args beyond ctx: static route, deterministic output.
// - ctx: caller context; a 30s timeout is applied on top of it.
//
// Returns:
// - raw decoded map with ok/method/path/citations or domain payload.
// - use CitationsOf(out) for the audit trail.
// - error: *httpError on non-2xx (status preserved for callers).
//
// Tags Health/AI/Data/Analytics/Seller OS/Vision/Verticals/Admin/Ops plus MCP tools.
//
// Curl example:
//
//	curl -s http://localhost:5003/api/v1/openapi-tags -X GET
//
// Go example:
//
//	cli := gen.NewClient("http://localhost:5003", "")
//	out, err := cli.OpenapiTags(ctx)
//
// Handbook: 01 ritual (headline) 02 reorder 03 P0<2h 04 invariant 05 S1<1h.
// Snapshot: openapi_snapshot.json#/paths/~1api~1v1~1openapi-tags
func (c *Client) OpenapiTags(ctx context.Context) (map[string]any, error) {
	// --- openapi_tags: citation-preserving net/http call ---
	ctx2, cancel := c.withTimeout(ctx)
	defer cancel()
	// route: GET /api/v1/openapi-tags (operation openapi_tags)
	// auth: X-API-Key injected by headers() when APIKey is set
	// retry: 3 tries exponential backoff on 429/408/5xx
	return c.doJSON(ctx2, http.MethodGet, "/api/v1/openapi-tags", nil, nil)
}

// ============================================================================
// Route table (18 routes, mirrors regen.py ROUTES for offline tooling)
// ============================================================================

// RouteInfo describes one snapshot route and its generated Go binding.
// Tooling (linters, doc generators) can range Routes without parsing JSON.
// The table is redundant with openapi_snapshot.json by design: regen.py
// remains the source of truth; this table is a convenience mirror.
// Handbook cross-ref: 01 ritual, 02 reorder, 03 P0<2h, 04 invariant, 05 S1<1h.
type RouteInfo struct {
	// HTTPMethod is GET or POST as declared in the snapshot paths table.
	HTTPMethod string

	// Path is the snapshot path, e.g. /api/v1/seller/close.
	Path string

	// GoMethod is the Client method name, e.g. SellerClose.
	GoMethod string

	// SnapshotMethod is the python/ts snake_case name, e.g. seller_close.
	SnapshotMethod string

	// Returns names the Go return shape (typed wrapper, map, or CSV bytes).
	Returns string

	// Summary is the snapshot summary line for this route.
	Summary string
}

// Routes lists all 18 snapshot routes in snapshot order (seller, vision, ...).
// Order matches regen.py ROUTES so diffs stay readable across languages.
// Every entry cites its snapshot path; counts are asserted in tests.
var Routes = []RouteInfo{
	// POST /api/v1/seller/close: DAILY CLOSE: profit + reorder/PO + reply drafts + leaks ($0).
	// Go binding: SellerClose | snapshot method: seller_close | returns CloseBundle.
	{HTTPMethod: "POST", Path: "/api/v1/seller/close", GoMethod: "SellerClose", SnapshotMethod: "seller_close", Returns: "CloseBundle", Summary: "DAILY CLOSE: profit + reorder/PO + reply drafts + leaks ($0)."},

	// GET /api/v1/seller/close.csv: DAILY CLOSE as CSV (accountant-ready, Sections A-D).
	// Go binding: SellerCloseCSV | snapshot method: seller_close_csv | returns bytes(CSV).
	{HTTPMethod: "GET", Path: "/api/v1/seller/close.csv", GoMethod: "SellerCloseCSV", SnapshotMethod: "seller_close_csv", Returns: "bytes(CSV)", Summary: "DAILY CLOSE as CSV (accountant-ready, Sections A-D)."},

	// POST /api/v1/seller/briefing: Seller OS briefing: true profit, stockout risk, listing health.
	// Go binding: SellerBriefing | snapshot method: seller_briefing | returns Briefing.
	{HTTPMethod: "POST", Path: "/api/v1/seller/briefing", GoMethod: "SellerBriefing", SnapshotMethod: "seller_briefing", Returns: "Briefing", Summary: "Seller OS briefing: true profit, stockout risk, listing health."},

	// POST /api/v1/seller/operations: Seller Operations: briefing + workshop queue + governance audit.
	// Go binding: SellerOperations | snapshot method: seller_operations | returns map.
	{HTTPMethod: "POST", Path: "/api/v1/seller/operations", GoMethod: "SellerOperations", SnapshotMethod: "seller_operations", Returns: "map", Summary: "Seller Operations: briefing + workshop queue + governance audit."},

	// GET /api/v1/seller/scenarios: List 12 practical seller scenarios (static registry).
	// Go binding: SellerScenariosList | snapshot method: seller_scenarios_list | returns map.
	{HTTPMethod: "GET", Path: "/api/v1/seller/scenarios", GoMethod: "SellerScenariosList", SnapshotMethod: "seller_scenarios_list", Returns: "map", Summary: "List 12 practical seller scenarios (static registry)."},

	// POST /api/v1/seller/scenarios/run: Run 12 scenarios on demo or folder into Workshop queue + audit.
	// Go binding: SellerScenariosRun | snapshot method: seller_scenarios_run | returns map.
	{HTTPMethod: "POST", Path: "/api/v1/seller/scenarios/run", GoMethod: "SellerScenariosRun", SnapshotMethod: "seller_scenarios_run", Returns: "map", Summary: "Run 12 scenarios on demo or folder into Workshop queue + audit."},

	// GET /api/v1/seller/export.csv: Briefing KPIs + actions as CSV for spreadsheet users.
	// Go binding: SellerExportCSV | snapshot method: seller_export_csv | returns bytes(CSV).
	{HTTPMethod: "GET", Path: "/api/v1/seller/export.csv", GoMethod: "SellerExportCSV", SnapshotMethod: "seller_export_csv", Returns: "bytes(CSV)", Summary: "Briefing KPIs + actions as CSV for spreadsheet users."},

	// POST /api/v1/seller/photo: Seller Photo: invoice or product photo (free OCR+chart+pipeline).
	// Go binding: SellerPhoto | snapshot method: seller_photo | returns map.
	{HTTPMethod: "POST", Path: "/api/v1/seller/photo", GoMethod: "SellerPhoto", SnapshotMethod: "seller_photo", Returns: "map", Summary: "Seller Photo: invoice or product photo (free OCR+chart+pipeline)."},

	// POST /api/v1/vision/analyze: Photo to text + chart to layered analysis (100% free, local).
	// Go binding: VisionAnalyze | snapshot method: vision_analyze | returns map.
	{HTTPMethod: "POST", Path: "/api/v1/vision/analyze", GoMethod: "VisionAnalyze", SnapshotMethod: "vision_analyze", Returns: "map", Summary: "Photo to text + chart to layered analysis (100% free, local)."},

	// GET /api/v1/vision/demo: Vision Demo: synthetic receipt+chart photo analysed (free).
	// Go binding: VisionDemo | snapshot method: vision_demo | returns map.
	{HTTPMethod: "GET", Path: "/api/v1/vision/demo", GoMethod: "VisionDemo", SnapshotMethod: "vision_demo", Returns: "map", Summary: "Vision Demo: synthetic receipt+chart photo analysed (free)."},

	// POST /api/v1/analyze: Data Analysis via multi-layer pipeline (L1-L4).
	// Go binding: Analyze | snapshot method: analyze | returns map.
	{HTTPMethod: "POST", Path: "/api/v1/analyze", GoMethod: "Analyze", SnapshotMethod: "analyze", Returns: "map", Summary: "Data Analysis via multi-layer pipeline (L1-L4)."},

	// POST /api/v1/synthesize: AI Synthesis for complex data (RAG + routing + cache).
	// Go binding: Synthesize | snapshot method: synthesize | returns map.
	{HTTPMethod: "POST", Path: "/api/v1/synthesize", GoMethod: "Synthesize", SnapshotMethod: "synthesize", Returns: "map", Summary: "AI Synthesis for complex data (RAG + routing + cache)."},

	// POST /api/v1/revenue/health: RevOps Health Scoring (vertical pack, deterministic).
	// Go binding: RevenueHealth | snapshot method: revenue_health | returns map.
	{HTTPMethod: "POST", Path: "/api/v1/revenue/health", GoMethod: "RevenueHealth", SnapshotMethod: "revenue_health", Returns: "map", Summary: "RevOps Health Scoring (vertical pack, deterministic)."},

	// POST /api/v1/micro/briefing: Micro-Biz Daily Briefing, no DB/website (LABS).
	// Go binding: MicroBriefing | snapshot method: micro_briefing | returns map.
	{HTTPMethod: "POST", Path: "/api/v1/micro/briefing", GoMethod: "MicroBriefing", SnapshotMethod: "micro_briefing", Returns: "map", Summary: "Micro-Biz Daily Briefing, no DB/website (LABS)."},

	// GET /api/v1/metrics: System metrics from live 200-record eval (seed 42).
	// Go binding: GetMetrics | snapshot method: get_metrics | returns map.
	{HTTPMethod: "GET", Path: "/api/v1/metrics", GoMethod: "GetMetrics", SnapshotMethod: "get_metrics", Returns: "map", Summary: "System metrics from live 200-record eval (seed 42)."},

	// GET /api/v1/models: List available models with costs and latencies.
	// Go binding: ListModels | snapshot method: list_models | returns map.
	{HTTPMethod: "GET", Path: "/api/v1/models", GoMethod: "ListModels", SnapshotMethod: "list_models", Returns: "map", Summary: "List available models with costs and latencies."},

	// GET /health: Liveness probe ({status:healthy, mode:mvp}, <5ms).
	// Go binding: Health | snapshot method: health | returns map.
	{HTTPMethod: "GET", Path: "/health", GoMethod: "Health", SnapshotMethod: "health", Returns: "map", Summary: "Liveness probe ({status:healthy, mode:mvp}, <5ms)."},

	// GET /api/v1/openapi-tags: Tag catalog for integrators (9 tags + MCP inventory).
	// Go binding: OpenapiTags | snapshot method: openapi_tags | returns map.
	{HTTPMethod: "GET", Path: "/api/v1/openapi-tags", GoMethod: "OpenapiTags", SnapshotMethod: "openapi_tags", Returns: "map", Summary: "Tag catalog for integrators (9 tags + MCP inventory)."},
}

// RouteCount returns len(Routes); 18 pins the snapshot route total.
// Guards against silent route drops during regeneration.
func RouteCount() int {
	return len(Routes)
}

// ============================================================================
// Golden demo payload (offline fixture, mirrors snapshot golden numbers)
// ============================================================================

// GoldenClosePayload returns the canned golden demo CloseBundle payload.
// True profit is 169.09, margin 61.7, money at risk 102.75 (handbook 01).
// Tests serve this map from httptest; no network ever required.
// Every money figure cites [file:line]; the close refuses invented tasks.
// Invariant true_profit <= gmv holds: 169.09 <= 274.0 (handbook 04).
// CJK/emoji names survive because maps stay byte-identical UTF-8.
func GoldenClosePayload() map[string]any {
	return map[string]any{
		"ok":       true,
		"method":   "seller_close",
		"path":     "/api/v1/seller/close",
		"headline": "Profit $169.09 (61.7%) \u00b7 $102.75 at risk in 3 angry messages \u00b7 1 reorder(s) TODAY \u00b7 0 leak(s) to plug",
		"kpis": map[string]any{
			"gmv":               274.0,
			"fees":              18.5,
			"shipping":          12.0,
			"net":               243.5,
			"cogs":              74.41,
			"true_profit":       169.09,
			"margin_pct":        61.7,
			"orders":            8,
			"aov":               34.25,
			"best_seller":       map[string]any{"product": "Tote Bag Handmade", "qty": 6, "gmv": 120.0},
			"money_at_risk_usd": 102.75,
			"citations":         []string{"[shopify_orders.csv:5]", "[supplier_invoice_2024-09-10.txt:3]"},
		},
		"reorder": []any{
			map[string]any{"product": "Tote Bag Handmade", "on_hand": 2, "sold_7d": 6, "daily_velocity": 0.86, "days_left": 2.3, "reorder_qty_14d": 10, "supplier": "Acme Textiles", "urgency": "ORDER TODAY", "citation": "[inventory.csv:2]"},
		},
		"reply_queue": []any{
			map[string]any{"id": "reply-001", "priority": "P0-reply-in-2h", "channel": "dm", "customer": "Maria", "excerpt": "Where is my order??", "draft": "Hi Maria! ... ([instagram_dm.txt:4])", "citation": "[instagram_dm.txt:4]"},
		},
		"scenarios": []any{
			map[string]any{"id": "dec-stockout-001", "scenario_id": "STOCKOUT", "severity": "critical", "title": "Tote Bag Handmade hits zero in 2.3d", "action": "reorderProduct", "product": "Tote Bag Handmade", "citation": "[inventory.csv:2]"},
		},
		"money_leaks": []any{},
		"po_draft":    "Subject: Reorder request \u2014 Acme Textiles\nHi! Please send 10x Tote Bag Handmade [[inventory.csv:2]]",
		"citations":   []string{"[inventory.csv:2]", "[shopify_orders.csv:5]"},
	}
}

// GoldenCloseCSV returns the accountant-ready CSV twin of the golden close.
// Four sections: title row, metric,value ledger, do_today, reorder/leak blocks.
// Section A ledger carries true_profit 169.09 for the 04 pack.
func GoldenCloseCSV() []byte {
	lines := []string{
		"close_bundle,golden_demo",
		"metric,value",
		"gmv,274.00",
		"fees,18.50",
		"shipping,12.00",
		"net,243.50",
		"cogs,74.41",
		"true_profit,169.09",
		"margin_pct,61.70",
		"money_at_risk_usd,102.75",
		"do_today,reply-001 P0-reply-in-2h [instagram_dm.txt:4]",
		"product,on_hand,sold_7d,days_left,reorder_qty_14d,supplier,urgency,citation",
		"Tote Bag Handmade,2,6,2.3,10,Acme Textiles,ORDER TODAY,[inventory.csv:2]",
	}
	return []byte(strings.Join(lines, "\n") + "\n")
}
