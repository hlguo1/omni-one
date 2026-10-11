// GENERATED from openapi_snapshot.json — do not hand-edit
// Contract tests for the GENERATED Go client (stdlib testing + httptest only).
// Spins an httptest server with canned golden payloads; no network required.
// Golden demo: true_profit 169.09, margin 61.7, money at risk 102.75.
package gen

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync"
	"sync/atomic"
	"testing"
	"time"
)

// cannedCloseJSON is the golden DAILY CLOSE payload served by tests.
// True profit 169.09 (handbook 01); invariant true_profit <= gmv holds.
const cannedCloseJSON = `{
  "ok": true,
  "method": "seller_close",
  "path": "/api/v1/seller/close",
  "headline": "Profit $169.09 (61.7%) \u00b7 $102.75 at risk in 3 angry messages \u00b7 1 reorder(s) TODAY \u00b7 0 leak(s) to plug",
  "kpis": {
    "gmv": 274.0,
    "fees": 18.5,
    "shipping": 12.0,
    "net": 243.5,
    "cogs": 74.41,
    "true_profit": 169.09,
    "margin_pct": 61.7,
    "orders": 8,
    "aov": 34.25,
    "best_seller": {"product": "Tote Bag Handmade", "qty": 6, "gmv": 120.0},
    "money_at_risk_usd": 102.75,
    "citations": ["[shopify_orders.csv:5]", "[supplier_invoice_2024-09-10.txt:3]"]
  },
  "reorder": [
    {"product": "Tote Bag Handmade", "on_hand": 2, "sold_7d": 6, "daily_velocity": 0.86, "days_left": 2.3, "reorder_qty_14d": 10, "supplier": "Acme Textiles", "urgency": "ORDER TODAY", "citation": "[inventory.csv:2]"}
  ],
  "reply_queue": [
    {"id": "reply-001", "priority": "P0-reply-in-2h", "channel": "dm", "customer": "Maria", "excerpt": "Where is my order??", "draft": "Hi Maria! ... ([instagram_dm.txt:4])", "citation": "[instagram_dm.txt:4]"}
  ],
  "scenarios": [
    {"id": "dec-stockout-001", "scenario_id": "STOCKOUT", "severity": "critical", "title": "Tote Bag Handmade hits zero in 2.3d", "action": "reorderProduct", "product": "Tote Bag Handmade", "citation": "[inventory.csv:2]"}
  ],
  "money_leaks": [],
  "po_draft": "Subject: Reorder request \u2014 Acme Textiles\nHi! Please send 10x Tote Bag Handmade [[inventory.csv:2]]",
  "citations": ["[inventory.csv:2]", "[shopify_orders.csv:5]"]
}`

// cannedCloseCSV is the accountant-ready CSV twin (Sections A-D ledger).
const cannedCloseCSV = "close_bundle,golden_demo\n" +
	"metric,value\n" +
	"gmv,274.00\n" +
	"fees,18.50\n" +
	"shipping,12.00\n" +
	"net,243.50\n" +
	"cogs,74.41\n" +
	"true_profit,169.09\n" +
	"margin_pct,61.70\n" +
	"money_at_risk_usd,102.75\n" +
	"do_today,reply-001 P0-reply-in-2h [instagram_dm.txt:4]\n" +
	"product,on_hand,sold_7d,days_left,reorder_qty_14d,supplier,urgency,citation\n" +
	"Tote Bag Handmade,2,6,2.3,10,Acme Textiles,ORDER TODAY,[inventory.csv:2]\n"

// recorder captures headers + bodies seen by the httptest server.
// It proves X-API-Key auth, multipart uploads, and JSON bodies offline.
type recorder struct {
	mu       sync.Mutex
	apiKeys  map[string]string
	bodies   map[string]string
	ctypes   map[string]string
	counters map[string]*int64
}

// newRecorder builds an empty request recorder for one test server.
func newRecorder() *recorder {
	return &recorder{
		apiKeys:  map[string]string{},
		bodies:   map[string]string{},
		ctypes:   map[string]string{},
		counters: map[string]*int64{},
	}
}

// count returns the per-path hit counter, creating it on first use.
func (r *recorder) count(path string) *int64 {
	r.mu.Lock()
	defer r.mu.Unlock()
	c, ok := r.counters[path]
	if !ok {
		c = new(int64)
		r.counters[path] = c
	}
	return c
}

// hits returns how many times path was requested (for retry assertions).
func (r *recorder) hits(path string) int64 {
	r.mu.Lock()
	c, ok := r.counters[path]
	r.mu.Unlock()
	if !ok || c == nil {
		return 0
	}
	return atomic.LoadInt64(c)
}

// note records headers + body for path in a race-safe way.
func (r *recorder) note(req *http.Request, body []byte, path string) {
	r.mu.Lock()
	defer r.mu.Unlock()
	r.apiKeys[path] = req.Header.Get(APIKeyHeader)
	r.bodies[path] = string(body)
	r.ctypes[path] = req.Header.Get("Content-Type")
}

// jsonOK writes a generic citation-preserving JSON envelope for path.
func jsonOK(w http.ResponseWriter, method, path string) {
	w.Header().Set("Content-Type", "application/json")
	fmt.Fprintf(w, `{"ok": true, "method": %q, "path": %q, "citations": ["[inventory.csv:2]"]}`, method, path)
}

// testServer builds the canned httptest backend shared by contract tests.
// Routes: close JSON, close.csv bytes, export.csv bytes, multipart echo,
// retry-once 429 (for /seller/scenarios), generic JSON everywhere else.
func testServer(t *testing.T, rec *recorder) *httptest.Server {
	t.Helper()
	mux := http.NewServeMux()
	// Golden close JSON (profit 169.09 fixture).
	mux.HandleFunc("/api/v1/seller/close", func(w http.ResponseWriter, req *http.Request) {
		body := readAll(t, req)
		rec.note(req, body, req.URL.Path)
		atomic.AddInt64(rec.count(req.URL.Path), 1)
		w.Header().Set("Content-Type", "application/json")
		fmt.Fprint(w, cannedCloseJSON)
	})
	// CSV twins return raw bytes (Content-Disposition attachment).
	csvHandler := func(w http.ResponseWriter, req *http.Request) {
		rec.note(req, nil, req.URL.Path)
		atomic.AddInt64(rec.count(req.URL.Path), 1)
		w.Header().Set("Content-Type", "text/csv")
		w.Header().Set("Content-Disposition", "attachment; filename=close.csv")
		fmt.Fprint(w, cannedCloseCSV)
	}
	mux.HandleFunc("/api/v1/seller/close.csv", csvHandler)
	mux.HandleFunc("/api/v1/seller/export.csv", csvHandler)
	// Multipart uploads echo a JSON envelope (photo + vision share it).
	multipartHandler := func(w http.ResponseWriter, req *http.Request) {
		atomic.AddInt64(rec.count(req.URL.Path), 1)
		if err := req.ParseMultipartForm(10 << 20); err != nil {
			http.Error(w, "bad multipart: "+err.Error(), http.StatusBadRequest)
			return
		}
		rec.note(req, nil, req.URL.Path)
		jsonOK(w, "upload", req.URL.Path)
	}
	mux.HandleFunc("/api/v1/seller/photo", multipartHandler)
	mux.HandleFunc("/api/v1/vision/analyze", multipartHandler)
	// Scenarios list fails once with 429, then succeeds (retry proof).
	mux.HandleFunc("/api/v1/seller/scenarios", func(w http.ResponseWriter, req *http.Request) {
		n := atomic.AddInt64(rec.count(req.URL.Path), 1)
		rec.note(req, nil, req.URL.Path)
		if n == 1 {
			http.Error(w, `{"detail": "Rate limited. Try again shortly."}`, http.StatusTooManyRequests)
			return
		}
		jsonOK(w, "seller_scenarios_list", req.URL.Path)
	})
	// Every other route echoes a generic citation-preserving envelope.
	for _, p := range []string{
		"/api/v1/seller/briefing",
		"/api/v1/seller/operations",
		"/api/v1/seller/scenarios/run",
		"/api/v1/vision/demo",
		"/api/v1/analyze",
		"/api/v1/synthesize",
		"/api/v1/revenue/health",
		"/api/v1/micro/briefing",
		"/api/v1/metrics",
		"/api/v1/models",
		"/health",
		"/api/v1/openapi-tags",
	} {
		p := p
		mux.HandleFunc(p, func(w http.ResponseWriter, req *http.Request) {
			body := readAll(t, req)
			rec.note(req, body, req.URL.Path)
			atomic.AddInt64(rec.count(req.URL.Path), 1)
			jsonOK(w, "echo", p)
		})
	}
	return httptest.NewServer(mux)
}

// readAll drains a request body for recording (tests only, tiny payloads).
func readAll(t *testing.T, req *http.Request) []byte {
	t.Helper()
	if req.Body == nil {
		return nil
	}
	b := make([]byte, 0, 512)
	buf := make([]byte, 512)
	for {
		n, err := req.Body.Read(buf)
		if n > 0 {
			b = append(b, buf[:n]...)
		}
		if err != nil {
			break
		}
	}
	return b
}

// ctx30 returns a 30s-bounded context for contract calls (mirrors default).
func ctx30(t *testing.T) context.Context {
	t.Helper()
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	t.Cleanup(cancel)
	return ctx
}

// TestVersionPin asserts GeneratedVersion tracks the snapshot (1.1.0).
func TestVersionPin(t *testing.T) {
	if GeneratedVersion != "1.1.0" {
		t.Fatalf("GeneratedVersion = %q, want 1.1.0", GeneratedVersion)
	}
	if SnapshotFile != "openapi_snapshot.json" {
		t.Fatalf("SnapshotFile = %q, want openapi_snapshot.json", SnapshotFile)
	}
	if DefaultTimeoutSecs != 30.0 {
		t.Fatalf("DefaultTimeoutSecs = %v, want 30", DefaultTimeoutSecs)
	}
	if DefaultRetries != 3 {
		t.Fatalf("DefaultRetries = %v, want 3", DefaultRetries)
	}
}

// TestRouteTableCovers18 asserts the Routes mirror holds all 18 snapshot routes.
func TestRouteTableCovers18(t *testing.T) {
	if RouteCount() != 18 {
		t.Fatalf("RouteCount() = %d, want 18", RouteCount())
	}
	want := map[string]bool{
		"SellerClose": false, "SellerCloseCSV": false, "SellerBriefing": false,
		"SellerOperations": false, "SellerScenariosList": false, "SellerScenariosRun": false,
		"SellerExportCSV": false, "SellerPhoto": false, "VisionAnalyze": false,
		"VisionDemo": false, "Analyze": false, "Synthesize": false,
		"RevenueHealth": false, "MicroBriefing": false, "GetMetrics": false,
		"ListModels": false, "Health": false, "OpenapiTags": false,
	}
	for _, r := range Routes {
		if _, ok := want[r.GoMethod]; !ok {
			t.Fatalf("unexpected route method %q", r.GoMethod)
		}
		want[r.GoMethod] = true
	}
	for m, seen := range want {
		if !seen {
			t.Fatalf("route table missing %s", m)
		}
	}
}

// TestNewClientDefaults asserts constructor defaults (base URL, 30s timeout).
func TestNewClientDefaults(t *testing.T) {
	c := NewClient("", "")
	if c.BaseURL != DefaultBaseURL {
		t.Fatalf("BaseURL = %q, want %q", c.BaseURL, DefaultBaseURL)
	}
	if c.TimeoutSecs != DefaultTimeoutSecs {
		t.Fatalf("TimeoutSecs = %v, want %v", c.TimeoutSecs, DefaultTimeoutSecs)
	}
	if c.Client == nil {
		t.Fatal("embedded *http.Client is nil; want non-nil transport")
	}
	trimmed := NewClient("http://x:5003/", "")
	if strings.HasSuffix(trimmed.BaseURL, "/") {
		t.Fatalf("BaseURL %q keeps trailing slash", trimmed.BaseURL)
	}
}

// TestSellerCloseParsesHeadlineAndKPIs asserts the golden close decodes.
// Headline plus kpis (gmv, true_profit 169.09, money_at_risk_usd) must parse.
func TestSellerCloseParsesHeadlineAndKPIs(t *testing.T) {
	rec := newRecorder()
	srv := testServer(t, rec)
	defer srv.Close()
	cli := NewClient(srv.URL, "")
	cli.TimeoutSecs = 30
	bundle, err := cli.SellerClose(ctx30(t), CloseRequest{Demo: true, Seed: 42, Shop: "our shop"})
	if err != nil {
		t.Fatalf("SellerClose: %v", err)
	}
	if bundle == nil {
		t.Fatal("SellerClose returned nil bundle")
	}
	if !strings.Contains(bundle.Headline, "169.09") {
		t.Fatalf("headline %q lacks golden 169.09", bundle.Headline)
	}
	if bundle.KPIs.TrueProfit != 169.09 {
		t.Fatalf("true_profit = %v, want 169.09", bundle.KPIs.TrueProfit)
	}
	if bundle.KPIs.GMV != 274.0 {
		t.Fatalf("gmv = %v, want 274.0", bundle.KPIs.GMV)
	}
	if bundle.KPIs.MoneyAtRiskUSD != 102.75 {
		t.Fatalf("money_at_risk_usd = %v, want 102.75", bundle.KPIs.MoneyAtRiskUSD)
	}
	if len(bundle.Raw) == 0 {
		t.Fatal("Raw map passthrough is empty; citation-preserving requires Raw")
	}
	if len(bundle.CitationsList()) == 0 {
		t.Fatal("CitationsList() is empty; want [file:line] citations")
	}
	if !bundle.CheckInvariant() {
		t.Fatal("CheckInvariant() false on golden payload; want true_profit <= gmv")
	}
	if len(bundle.Reorder) != 1 || bundle.Reorder[0].Product != "Tote Bag Handmade" {
		t.Fatalf("reorder sheet mismatch: %+v", bundle.Reorder)
	}
	if len(bundle.ReplyQueue) != 1 || bundle.ReplyQueue[0].Draft == "" {
		t.Fatalf("reply_queue draft missing: %+v", bundle.ReplyQueue)
	}
	if bundle.PoDraft == "" {
		t.Fatal("po_draft missing from golden bundle")
	}
}

// TestSellerCloseCSVReturnsBytes asserts the CSV twin comes back as bytes.
func TestSellerCloseCSVReturnsBytes(t *testing.T) {
	rec := newRecorder()
	srv := testServer(t, rec)
	defer srv.Close()
	cli := NewClient(srv.URL, "")
	raw, err := cli.SellerCloseCSV(ctx30(t), map[string]string{"demo": "true", "seed": "42"})
	if err != nil {
		t.Fatalf("SellerCloseCSV: %v", err)
	}
	if len(raw) == 0 {
		t.Fatal("SellerCloseCSV returned empty bytes")
	}
	text := string(raw)
	if !strings.Contains(text, "true_profit,169.09") {
		t.Fatalf("CSV lacks true_profit row:\n%s", text)
	}
	if !strings.Contains(text, "[inventory.csv:2]") {
		t.Fatalf("CSV lacks citation:\n%s", text)
	}
	exp, err := cli.SellerExportCSV(ctx30(t), map[string]string{"demo": "true"})
	if err != nil {
		t.Fatalf("SellerExportCSV: %v", err)
	}
	if len(exp) == 0 {
		t.Fatal("SellerExportCSV returned empty bytes")
	}
}

// TestRetryOn429Then200 asserts 429-then-200 retries to success exactly twice.
func TestRetryOn429Then200(t *testing.T) {
	rec := newRecorder()
	srv := testServer(t, rec)
	defer srv.Close()
	cli := NewClient(srv.URL, "")
	out, err := cli.SellerScenariosList(ctx30(t))
	if err != nil {
		t.Fatalf("SellerScenariosList after 429: %v", err)
	}
	if out["ok"] != true {
		t.Fatalf("expected ok=true after retry, got %v", out)
	}
	if got := rec.hits("/api/v1/seller/scenarios"); got != 2 {
		t.Fatalf("hits = %d, want 2 (429 then 200)", got)
	}
}

// TestAPIKeyHeaderSent asserts X-API-Key travels on every authenticated call.
func TestAPIKeyHeaderSent(t *testing.T) {
	rec := newRecorder()
	srv := testServer(t, rec)
	defer srv.Close()
	cli := NewClient(srv.URL, "test-key-123")
	if _, err := cli.Health(ctx30(t)); err != nil {
		t.Fatalf("Health: %v", err)
	}
	rec.mu.Lock()
	got := rec.apiKeys["/health"]
	rec.mu.Unlock()
	if got != "test-key-123" {
		t.Fatalf("X-API-Key = %q, want test-key-123", got)
	}
	if _, err := cli.SellerClose(ctx30(t), CloseRequest{Demo: true}); err != nil {
		t.Fatalf("SellerClose: %v", err)
	}
	rec.mu.Lock()
	gotClose := rec.apiKeys["/api/v1/seller/close"]
	rec.mu.Unlock()
	if gotClose != "test-key-123" {
		t.Fatalf("close X-API-Key = %q, want test-key-123", gotClose)
	}
}

// TestFastFail400 asserts 400-class errors do NOT retry (single hit).
func TestFastFail400(t *testing.T) {
	var n int64
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, req *http.Request) {
		atomic.AddInt64(&n, 1)
		http.Error(w, `{"detail": "bad CSV header"}`, http.StatusBadRequest)
	}))
	defer srv.Close()
	cli := NewClient(srv.URL, "")
	if _, err := cli.Health(ctx30(t)); err == nil {
		t.Fatal("expected 400 error, got nil")
	}
	if atomic.LoadInt64(&n) != 1 {
		t.Fatalf("400 retried %d times, want exactly 1 (fast-fail)", n)
	}
}

// TestRetryableStatusTable pins the 429/408/5xx retry set (3 tries total).
func TestRetryableStatusTable(t *testing.T) {
	for _, s := range []int{429, 408, 500, 502, 503} {
		if !retryableStatus(s) {
			t.Fatalf("retryableStatus(%d) = false, want true", s)
		}
	}
	for _, s := range []int{200, 400, 401, 404} {
		if retryableStatus(s) {
			t.Fatalf("retryableStatus(%d) = true, want false", s)
		}
	}
	if got := backoffFor(0); got != 500*time.Millisecond {
		t.Fatalf("backoffFor(0) = %v, want 500ms", got)
	}
	if got := backoffFor(1); got != 1000*time.Millisecond {
		t.Fatalf("backoffFor(1) = %v, want 1s", got)
	}
}

// TestAll18MethodsReachable sweeps every method against the canned server.
// Each call must succeed and preserve citations or CSV bytes (no panics).
func TestAll18MethodsReachable(t *testing.T) {
	rec := newRecorder()
	srv := testServer(t, rec)
	defer srv.Close()
	cli := NewClient(srv.URL, "sweep-key")
	ctx := ctx30(t)
	if _, err := cli.SellerClose(ctx, CloseRequest{Demo: true, Seed: 42}); err != nil {
		t.Fatalf("SellerClose: %v", err)
	}
	if _, err := cli.SellerCloseCSV(ctx, nil); err != nil {
		t.Fatalf("SellerCloseCSV: %v", err)
	}
	if _, err := cli.SellerBriefing(ctx, BriefingRequest{Demo: true}); err != nil {
		t.Fatalf("SellerBriefing: %v", err)
	}
	if _, err := cli.SellerOperations(ctx, OperationsRequest{Demo: true}); err != nil {
		t.Fatalf("SellerOperations: %v", err)
	}
	// ScenariosList already proved retry; a second call now returns 200 directly.
	if _, err := cli.SellerScenariosList(ctx); err != nil {
		t.Fatalf("SellerScenariosList: %v", err)
	}
	if _, err := cli.SellerScenariosRun(ctx, ScenariosRunRequest{Demo: true}); err != nil {
		t.Fatalf("SellerScenariosRun: %v", err)
	}
	if _, err := cli.SellerExportCSV(ctx, nil); err != nil {
		t.Fatalf("SellerExportCSV: %v", err)
	}
	if _, err := cli.SellerPhoto(ctx, "invoice.jpg", []byte("fake-jpeg"), "eng"); err != nil {
		t.Fatalf("SellerPhoto: %v", err)
	}
	if _, err := cli.VisionAnalyze(ctx, "receipt.jpg", []byte("fake-jpeg"), "eng"); err != nil {
		t.Fatalf("VisionAnalyze: %v", err)
	}
	if _, err := cli.VisionDemo(ctx); err != nil {
		t.Fatalf("VisionDemo: %v", err)
	}
	if _, err := cli.Analyze(ctx, AnalyzeRequest{Records: []map[string]any{{"x": 1}}}); err != nil {
		t.Fatalf("Analyze: %v", err)
	}
	if _, err := cli.Synthesize(ctx, SynthesizeRequest{Query: "restock?"}); err != nil {
		t.Fatalf("Synthesize: %v", err)
	}
	if _, err := cli.RevenueHealth(ctx, RevenueHealthRequest{Accounts: 50, Seed: 42}); err != nil {
		t.Fatalf("RevenueHealth: %v", err)
	}
	if _, err := cli.MicroBriefing(ctx, MicroBriefingRequest{Demo: true}); err != nil {
		t.Fatalf("MicroBriefing: %v", err)
	}
	if _, err := cli.GetMetrics(ctx); err != nil {
		t.Fatalf("GetMetrics: %v", err)
	}
	if _, err := cli.ListModels(ctx); err != nil {
		t.Fatalf("ListModels: %v", err)
	}
	if _, err := cli.Health(ctx); err != nil {
		t.Fatalf("Health: %v", err)
	}
	if _, err := cli.OpenapiTags(ctx); err != nil {
		t.Fatalf("OpenapiTags: %v", err)
	}
}

// TestTypedWrappersRoundTrip asserts FromMap/ToMap keep raw + citations.
func TestTypedWrappersRoundTrip(t *testing.T) {
	var m map[string]any
	if err := json.Unmarshal([]byte(cannedCloseJSON), &m); err != nil {
		t.Fatalf("fixture unmarshal: %v", err)
	}
	bundle, err := CloseBundleFromMap(m)
	if err != nil {
		t.Fatalf("CloseBundleFromMap: %v", err)
	}
	if len(bundle.ToMap()) == 0 {
		t.Fatal("ToMap() empty; want raw passthrough")
	}
	k, err := KPIsFromMap(bundle.KPIs.ToMap())
	if err != nil {
		t.Fatalf("KPIsFromMap: %v", err)
	}
	if k.TrueProfit != 169.09 || k.GMV != 274.0 || k.MoneyAtRiskUSD != 102.75 {
		t.Fatalf("KPI round-trip mismatch: %+v", k)
	}
	// reorder_sheet alias parses into Reorder (server variance tolerance).
	alias := map[string]any{"reorder_sheet": m["reorder"], "kpis": m["kpis"], "headline": m["headline"]}
	ab, err := CloseBundleFromMap(alias)
	if err != nil {
		t.Fatalf("alias FromMap: %v", err)
	}
	if len(ab.Reorder) != 1 || ab.Reorder[0].Citation != "[inventory.csv:2]" {
		t.Fatalf("reorder_sheet alias failed: %+v", ab.Reorder)
	}
	// Briefing + decision wrappers keep citations too.
	bm := map[string]any{"kpis": m["kpis"], "headline": m["headline"], "citations": m["citations"]}
	brief, err := BriefingFromMap(bm)
	if err != nil {
		t.Fatalf("BriefingFromMap: %v", err)
	}
	if len(brief.CitationsList()) == 0 {
		t.Fatal("Briefing citations empty")
	}
	dec, err := ScenarioDecisionFromMap(map[string]any{"id": "d1", "citation": "[inventory.csv:2]"})
	if err != nil {
		t.Fatalf("ScenarioDecisionFromMap: %v", err)
	}
	if len(dec.CitationsList()) == 0 {
		t.Fatal("ScenarioDecision citations empty")
	}
	rep, err := ReplyItemFromMap(map[string]any{"id": "reply-001", "draft": "hi", "citation": "[instagram_dm.txt:4]"})
	if err != nil {
		t.Fatalf("ReplyItemFromMap: %v", err)
	}
	if rep.Draft != "hi" {
		t.Fatalf("ReplyItem draft = %q, want hi", rep.Draft)
	}
	rl, err := ReorderLineFromMap(map[string]any{"product": "Tote Bag Handmade", "citation": "[inventory.csv:2]"})
	if err != nil {
		t.Fatalf("ReorderLineFromMap: %v", err)
	}
	if rl.Product != "Tote Bag Handmade" {
		t.Fatalf("ReorderLine product = %q", rl.Product)
	}
}

// TestGoldenHelpersMatchFixture asserts Golden* helpers equal canned values.
func TestGoldenHelpersMatchFixture(t *testing.T) {
	g := GoldenClosePayload()
	kraw, ok := g["kpis"].(map[string]any)
	if !ok {
		t.Fatal("golden kpis block missing")
	}
	if kraw["true_profit"] != 169.09 {
		t.Fatalf("golden true_profit = %v", kraw["true_profit"])
	}
	if !CheckInvariantClose(g) {
		t.Fatal("golden payload violates true_profit <= gmv")
	}
	if len(CitationsOf(g)) == 0 {
		t.Fatal("golden citations empty")
	}
	csv := string(GoldenCloseCSV())
	if !strings.Contains(csv, "true_profit,169.09") {
		t.Fatalf("golden CSV lacks ledger row:\n%s", csv)
	}
}

// TestRequestToMaps asserts the 8 request bodies encode expected keys.
func TestRequestToMaps(t *testing.T) {
	if m := (CloseRequest{Demo: true, Seed: 42}).ToMap(); m["demo"] != true {
		t.Fatalf("CloseRequest map: %v", m)
	}
	if m := (BriefingRequest{Demo: true}).ToMap(); m["demo"] != true {
		t.Fatalf("BriefingRequest map: %v", m)
	}
	if m := (OperationsRequest{Demo: true}).ToMap(); m["demo"] != true {
		t.Fatalf("OperationsRequest map: %v", m)
	}
	if m := (ScenariosRunRequest{Demo: true}).ToMap(); m["demo"] != true {
		t.Fatalf("ScenariosRunRequest map: %v", m)
	}
	if m := (AnalyzeRequest{Records: []map[string]any{{"a": 1}}}).ToMap(); m["records"] == nil {
		t.Fatalf("AnalyzeRequest map: %v", m)
	}
	if m := (SynthesizeRequest{Query: "q?"}).ToMap(); m["query"] != "q?" {
		t.Fatalf("SynthesizeRequest map: %v", m)
	}
	if m := (RevenueHealthRequest{Accounts: 50}).ToMap(); m["accounts"] == nil {
		t.Fatalf("RevenueHealthRequest map: %v", m)
	}
	if m := (MicroBriefingRequest{Demo: true}).ToMap(); m["demo"] != true {
		t.Fatalf("MicroBriefingRequest map: %v", m)
	}
}
