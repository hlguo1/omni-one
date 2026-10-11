# Incidents — stockout / 1-star / fee-spike runbooks

> Incidents are won in the first hour. Each runbook below follows the same
> shape: **detect** (what the close shows) → **triage** (severity table) →
> **act** (numbered steps with time boxes) → **follow up** (so it doesn't
> recur). Print this page. When the alert fires, start the timer.

## Severity scale (all runbooks)

| Sev | Meaning | Response time | Who |
|---|---|---|---|
| S1 critical | Losing money *right now* (chargeback, stockout of #1 seller, account warning) | < 1h | you, drop everything |
| S2 high | Will cost money within days (2d of stock, 1-star gaining views, fee jump) | < 4h | you, today |
| S3 medium | Margin erosion / slow bleed | this week | scheduled block |
| S4 low | Watch item, no action | note + recheck | next close |

---

## Runbook A — STOCKOUT (best seller about to hit zero)

**Detect:** `reorder.csv` shows your #1 seller `ORDER TODAY` (`days_left` < 3),
or the briefing alert reads `Stockout risk: X only N left, D days supply`
with citation `[inventory.csv:N]`.

### Severity

| Signal | Sev |
|---|---|
| `days_left` < 1 on top-3 seller | S1 |
| `days_left` 1–3 on any seller | S2 |
| `days_left` 3–5 | S3 |
| No inventory file / product unmatched | S2 (blind = dangerous) |

### Act (S1/S2, 30-min box)
1. **[0–5] Confirm the numbers.** Open `[inventory.csv:line]` from the citation. Physically eyeball the shelf — is `on_hand` real? (Common: you sold 3 at a market and forgot to decrement.) Correct the CSV if wrong, re-run close.
2. **[5–10] Send the PO.** Copy `po.txt`, fill blanks, send. Ask for **tracking + split shipment** if partial stock exists ("send what you have today, rest ASAP").
3. **[10–15] Protect the listing.** If `days_left` < lead time: raise price 10–15% to slow velocity *or* set quantity caps *or* pause ads. A paused listing beats an oversold one (cancellations tank rankings + trigger refunds).
4. **[15–20] Message waiting buyers.** Anyone who DMs "where is my order" on this SKU gets template 19 (made-to-order ETA) *before* they get angry.
5. **[20–30] Line up the backup.** Supplier playbook §5: trial order to the backup supplier today if primary ETA > `days_left`.

### Follow up (48h)
- [ ] PO confirmed with ETA in writing? If not, escalate (call).
- [ ] Listing protection still on? Remove it the day stock lands (stale caps lose sales).
- [ ] Root cause: lead time slipped, velocity spiked, or count drifted? Fix the *cause*: standing PO day (e.g. every Monday), lower cover threshold for spiky SKUs, or a $20 barcode tally habit.

---

## Runbook B — 1-STAR REVIEW / REVIEW CRISIS

**Detect:** briefing `at_risk` jumps, close `reply_queue` gains a `review`
channel row, or scenarios list `REVIEW_CRISIS` with evidence `[reviews.csv:N]`.

### Severity

| Signal | Sev |
|---|---|
| 1★ on best seller + mentions safety/allergy/chargeback | S1 |
| 1–2★ with damage/late specifics, < 24h old | S2 |
| 1–2★ vague ("didn't like it"), older | S3 |
| 3★ constructive | S4 (thank + fix quietly) |

### Act (S1/S2, 45-min box)
1. **[0–5] Read, don't react.** Open the exact `[reviews.csv:line]`. Note the *verifiable* claim (chipped? late? wrong?). Check the order citation if identifiable.
2. **[5–15] Public reply (template 08).** Thank + apologise + state the fix + invite to DM. Never: argue facts, mention refunds publicly (invites extortion), or reply twice. One reply, then stop watching the thread.
3. **[15–25] Private DM (template 05/06).** Offer the *choice* (replacement OR refund) within the hour. Include the citation. For S1, lead with the refund — speed beats margin here.
4. **[25–35] Fix the cause for the *next* buyer.** Damaged → add packing step today (photo the new pack). Late → check the carrier batch. Wrong item → re-label the shelf bins now, not "later".
5. **[35–45] Log it.** One line: date, SKU, claim, true/false, cost (refund $X / reship $Y), fix. Three identical lines in a quarter = product/process change, not bad luck.

### Follow up (7 days)
- [ ] Buyer updated their review? (Polite ask *once*, template 15. Never pay for review changes — bannable.)
- [ ] Did the fix hold? Zero repeat complaints on that SKU for 2 weeks = closed.
- [ ] If the claim was false/abusive: report with your evidence trail (`replies.txt` + order citation). Move on — one bad review among twenty 5-stars converts *better* (authenticity effect). Don't nuke the listing over it.

---

## Runbook C — FEE SPIKE / MARGIN COLLAPSE

**Detect:** close `money_leaks` shows `fee_creep` (fees ≥ 12% of GMV), or
headline margin drops > 5 points week-over-week with similar GMV, or a
channel announces a fee change.

### Severity

| Signal | Sev |
|---|---|
| Blended margin < 0% (losing money per order) | S1 — stop paid traffic + pause worst SKU today |
| Blended margin 0–10% for 2+ weeks | S2 |
| Single-channel fee rise announced | S3 (model it this week) |
| Shipping cost drift (+$1/order trend) | S3 |

### Act (S1/S2, 60-min box)
1. **[0–10] Verify the math.** `close.csv` Section A: is the spike in `fees`, `shipping`, or `cogs`? Each has a different owner (channel, carrier, supplier). Don't renegotiate with the wrong party.
2. **[10–20] Fees → reprice or re-channel.** Rule of thumb: price increase needed ≈ `fee_delta / (1 − fee_rate)`. A 2-point fee rise on a $28 item ≈ +$0.60 — round to +$1 and bank the difference. Or shift volume: Etsy 6.5%+$0.20 vs Shopify 2.9%+$0.30 vs Amazon 15% — route the *next* 10 orders, not all of history.
3. **[20–30] Shipping → re-weigh.** Weigh your packed parcel (not the product). 80% of "fee spikes" are actually dimensional-weight or zone drift. Fix: right-size the box, switch to tracked-lettermail under the threshold, or bake shipping into price with "free shipping" (conversion usually covers it).
4. **[30–40] COGS → supplier review.** Supplier playbook §3 thresholds: +5% unannounced rise = email within 48h. COGS > 45% of retail on a top-3 SKU = reprice + renegotiate in parallel.
5. **[40–60] Kill or fix the worst seller.** `kpis.worst_seller` + `listing_fixes`: clearance (recover cash), bundle (raise AOV), or delist (stop the bleed). Sentimentality is not a strategy.

### Follow up (30 days)
- [ ] Margin back above 10% floor for 2 consecutive weeks?
- [ ] Price change stuck (no conversion collapse)? Watch units/day for 14 days post-change; revert if velocity halves.
- [ ] Fee monitoring habit: glance at `money_leaks` in every close (5 seconds). The close watches; you just have to look.

---

## Cross-incident rules

1. **One incident at a time.** Stockout + 1-star + fee spike together? Order: stockout (revenue stops) → 1-star (reputation) → fees (margin). Say it out loud.
2. **Write as you go.** Every action gets its citation pasted next to it. Future-you (and your accountant, and the channel dispute team) needs the trail.
3. **Time-box everything.** A perfect reply sent tomorrow loses to a good reply sent in 2 hours. The SLA is the product.
4. **Post-mortem, 5 lines max:** what fired, what you did, what it cost, what you'll change, date to verify. File it with the month's closes.
5. **Know when it's not an incident.** A single S4, a margin wobble inside ±2 points, a slow Tuesday — note it, close the laptop, go pack orders. The system is working; let it.
