// Command example demonstrates the Omni-One Go SDK against a live server.
//
// Run a server first, then:
//
//	go run ./example
//
// Env:
//
//	OMNI_ONE_BASE_URL (default http://localhost:5003)
//	OMNI_ONE_API_KEY  (optional; sent as X-API-Key)
//
// Offline note: without a server this prints the connection error and exits
// non-zero. The python contract test (tests/unit/test_sdk_contract.py) never
// runs this — it validates client.go statically (no network).
package main

import (
	"context"
	"fmt"
	"os"
	"time"

	omnionego "github.com/omni-one/sdk-go"
)

func main() {
	base := os.Getenv("OMNI_ONE_BASE_URL")
	if base == "" {
		base = "http://localhost:5003"
	}
	c := omnionego.NewClient(base, os.Getenv("OMNI_ONE_API_KEY"))
	ctx, cancel := context.WithTimeout(context.Background(), 60*time.Second)
	defer cancel()

	// 1. Health.
	h, err := c.Health(ctx)
	if err != nil {
		fmt.Fprintf(os.Stderr, "health failed (is `omni-one serve` running on %s?): %v\n", base, err)
		os.Exit(1)
	}
	fmt.Printf("health: status=%s mode=%s service=%s\n", h.Status, h.Mode, h.Service)

	// 2. Demo briefing (golden: GMV 274.00 / true_profit 169.09).
	b, err := c.BriefingDemo(ctx, 42)
	if err != nil {
		fmt.Fprintf(os.Stderr, "briefing failed: %v\n", err)
		os.Exit(1)
	}
	fmt.Printf("briefing: GMV=%.2f profit=%.2f margin=%.1f%% orders=%d\n",
		b.KPIs.GMV, b.KPIs.TrueProfit, b.KPIs.MarginPct, b.KPIs.Orders)

	// 3. Scenarios.
	s, err := c.ScenariosRun(ctx, omnionego.ScenariosRunOptions{Demo: true, Seed: 42})
	if err != nil {
		fmt.Fprintf(os.Stderr, "scenarios failed: %v\n", err)
		os.Exit(1)
	}
	fmt.Printf("scenarios: total=%d\n", s.Total)

	// 4. Daily close (profit, reorder+PO, reply drafts, leaks — all cited).
	close, err := c.Close(ctx, omnionego.CloseOptions{Demo: true, Seed: 42, Shop: "our shop"})
	if err != nil {
		fmt.Fprintf(os.Stderr, "close failed: %v\n", err)
		os.Exit(1)
	}
	fmt.Printf("close: %s\n", close.Headline)
	fmt.Printf("  true_profit=%.2f at_risk=%.2f\n", close.KPIs.TrueProfit, close.KPIs.MoneyAtRiskUSD)
	if len(close.ReorderSheet) > 0 {
		r0 := close.ReorderSheet[0]
		// Citation passes through verbatim (file:line preserved).
		fmt.Printf("  reorder[0]: %s x%d [%s] urgency=%s\n", r0.Product, r0.ReorderQty, r0.Citation, r0.Urgency)
	}
	if len(close.ReplyQueue) > 0 {
		q0 := close.ReplyQueue[0]
		fmt.Printf("  reply[0]: %.60s... [%s]\n", q0.Draft, q0.Citation)
	}
	fmt.Printf("  po: %.60s...\n", close.PODraft)

	// 5. CSV bundle (rendered locally, citations intact).
	csvs, err := c.CloseCSV(ctx, omnionego.CloseOptions{Demo: true})
	if err != nil {
		fmt.Fprintf(os.Stderr, "closeCSV failed: %v\n", err)
		os.Exit(1)
	}
	fmt.Printf("csv bytes: close=%d reorder=%d replies=%d po=%d\n",
		len(csvs.CloseCSV), len(csvs.ReorderCSV), len(csvs.RepliesTxt), len(csvs.POTxt))

	// 6. Accountant validation (close.go helpers).
	summary := omnionego.SummariseClose(close)
	fmt.Printf("summary: profit=%.2f margin=%.1f%% replies=%d today=%d citation=%s\n",
		summary.TrueProfit, summary.MarginPct, summary.ReplyCount, summary.ReorderToday, summary.Citation)
	if problems := omnionego.ValidateCloseForAccountant(close); len(problems) > 0 {
		fmt.Printf("accountant warnings: %v\n", problems)
	} else {
		fmt.Println("accountant check: packable (all citations present)")
	}
}
