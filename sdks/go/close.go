// Close helpers for the Omni-One Go SDK (daily-close ritual bundle).
//
// This file holds the close-specific accessors + validators that sit on top
// of the CloseBundle struct in client.go. Citation rule (load-bearing):
// every helper copies Citation / Evidence / Draft / PODraft strings VERBATIM
// (file:line preserved). Never strip, lowercase, truncate, or re-map them.
//
// Contract fields used here (keep json tags in client.go exact):
// headline, kpis { gmv, true_profit, money_at_risk_usd },
// reorder_sheet[0] { product, reorder_qty, citation },
// reply_queue[0] { draft, citation }, po_draft.
package omnionego

import (
	"fmt"
	"strings"
)

// CloseSummary is one flattened close row (for tables / weekly trends).
type CloseSummary struct {
	// Date wall-clock day.
	Date string
	// Shop label.
	Shop string
	// Headline verbatim.
	Headline string
	// GMV value.
	GMV float64
	// TrueProfit value.
	TrueProfit float64
	// MarginPct value.
	MarginPct float64
	// MoneyAtRiskUSD value.
	MoneyAtRiskUSD float64
	// Orders count.
	Orders int
	// ReplyCount messages needing replies.
	ReplyCount int
	// ReorderToday ORDER TODAY lines.
	ReorderToday int
	// TopProduct first reorder row product.
	TopProduct string
	// TopReorderQty first reorder row qty.
	TopReorderQty int
	// Citation first available file:line (verbatim).
	Citation string
	// PODraftPresent whether po_draft is non-empty.
	PODraftPresent bool
}

// SummariseClose flattens a CloseBundle to one CloseSummary (deterministic).
//
// Citation selection: first reorder citation, else first reply citation,
// else first leak evidence — all verbatim (file:line passthrough).
func SummariseClose(b *CloseBundle) CloseSummary {
	s := CloseSummary{}
	if b == nil {
		return s
	}
	s.Date = b.Date
	s.Shop = b.Shop
	s.Headline = b.Headline
	s.GMV = b.KPIs.GMV
	s.TrueProfit = b.KPIs.TrueProfit
	s.MarginPct = b.KPIs.MarginPct
	s.MoneyAtRiskUSD = b.KPIs.MoneyAtRiskUSD
	s.Orders = b.KPIs.Orders
	s.ReplyCount = len(b.ReplyQueue)
	for _, r := range b.ReorderSheet {
		if r.Urgency == "ORDER TODAY" {
			s.ReorderToday++
		}
	}
	if len(b.ReorderSheet) > 0 {
		s.TopProduct = b.ReorderSheet[0].Product
		s.TopReorderQty = b.ReorderSheet[0].ReorderQty
		s.Citation = b.ReorderSheet[0].Citation
	}
	if s.Citation == "" && len(b.ReplyQueue) > 0 {
		s.Citation = b.ReplyQueue[0].Citation
	}
	if s.Citation == "" {
		for _, lk := range b.MoneyLeaks {
			if lk.Evidence != "" {
				s.Citation = lk.Evidence
				break
			}
		}
	}
	s.PODraftPresent = strings.TrimSpace(b.PODraft) != ""
	return s
}

// ValidateCloseForAccountant checks the accountant-critical fields and
// returns human-readable problems (empty = packable). Deterministic.
func ValidateCloseForAccountant(b *CloseBundle) []string {
	var problems []string
	if b == nil {
		return []string{"nil close bundle"}
	}
	if strings.TrimSpace(b.Headline) == "" {
		problems = append(problems, "headline empty")
	}
	if b.KPIs.Orders == 0 {
		problems = append(problems, "kpis.orders is 0 (no orders ingested?)")
	}
	if len(b.ReorderSheet) == 0 {
		problems = append(problems, "reorder_sheet empty (nothing to reorder or ingest failed)")
	} else {
		r0 := b.ReorderSheet[0]
		if strings.TrimSpace(r0.Product) == "" {
			problems = append(problems, "reorder_sheet[0].product empty")
		}
		if strings.TrimSpace(r0.Citation) == "" {
			problems = append(problems, "reorder_sheet[0].citation empty (citation stripped?)")
		} else if !strings.Contains(r0.Citation, ".csv:") && !strings.Contains(r0.Citation, ".txt:") {
			problems = append(problems, fmt.Sprintf("reorder_sheet[0].citation missing file:line: %q", r0.Citation))
		}
	}
	if len(b.ReplyQueue) == 0 {
		problems = append(problems, "reply_queue empty (nothing to answer or ingest failed)")
	} else {
		q0 := b.ReplyQueue[0]
		if len(q0.Draft) < 40 {
			problems = append(problems, "reply_queue[0].draft too short (<40 chars)")
		}
		if strings.TrimSpace(q0.Citation) == "" {
			problems = append(problems, "reply_queue[0].citation empty (citation stripped?)")
		}
	}
	if !strings.Contains(b.PODraft, "Subject: Reorder") {
		problems = append(problems, "po_draft missing 'Subject: Reorder' header")
	}
	return problems
}

// FormatCloseHeadline renders the one-line owner summary with a citation
// suffix (headline verbatim + first citation in brackets).
func FormatCloseHeadline(b *CloseBundle) string {
	if b == nil {
		return "(nil close)"
	}
	s := SummariseClose(b)
	if s.Citation != "" {
		return fmt.Sprintf("%s [%s]", b.Headline, s.Citation)
	}
	return b.Headline
}

// FormatShopRank renders one ranked compare row (see multi-shop compare).
func FormatShopRank(rank int, s CloseSummary) string {
	medal := ""
	switch rank {
	case 1:
		medal = " 🥇"
	case 2:
		medal = " 🥈"
	case 3:
		medal = " 🥉"
	}
	return fmt.Sprintf("%d%s | %s | $%.2f | %.1f%% | citation %s",
		rank, medal, s.Shop, s.TrueProfit, s.MarginPct, s.Citation)
}
