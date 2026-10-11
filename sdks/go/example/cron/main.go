// Command cron-run: 7am Daily Close for one shop via the generated client.
//
// Usage: SHOP=acme FOLDER=/data/inbox go run ./example/cron
package main

import (
	"fmt"
	"log"
	"os"
	"time"

	gen "omni-one-gen"
)

func main() {
	base := os.Getenv("OMNI_BASE")
	if base == "" {
		base = "http://localhost:5003"
	}
	folder := os.Getenv("FOLDER")
	shop := os.Getenv("SHOP")
	if shop == "" {
		shop = "our shop"
	}
	c := gen.NewClient(base, os.Getenv("OMNI_API_KEY"), 30)
	req := gen.CloseRequest{Folder: folder, Shop: shop, Seed: 42}
	if folder == "" {
		req.Demo = true
	}
	b, err := c.SellerClose(req)
	if err != nil {
		log.Fatalf("close failed: %v", err)
	}
	day := time.Now().Format("2006-01-02")
	out := fmt.Sprintf("./close_%s_%s.txt", shop, day)
	headline := fmt.Sprintf("%s | risk=%.2f", b.Headline, b.KPIs.MoneyAtRiskUSD)
	if err := os.WriteFile(out, []byte(headline+"\n"), 0o644); err != nil {
		log.Fatalf("write: %v", err)
	}
	fmt.Printf("CLOSE %s -> %s\n%s\n", day, out, headline)
	for i, t := range b.DoToday {
		fmt.Printf("  %d. %s\n", i+1, t)
	}
}
