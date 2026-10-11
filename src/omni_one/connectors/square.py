"""Square connector -> canonical events."""
from __future__ import annotations
from typing import Dict, List, Any

try:
    from ._common import (
        canonicalize_headers, has_known_fields, parse_money_abs, parse_qty,
        parse_date, detect_currency_code, is_refund, build_event, norm_header,
    )
except Exception:
    from omni_one.connectors._common import (  # type: ignore
        canonicalize_headers, has_known_fields, parse_money_abs, parse_qty,
        parse_date, detect_currency_code, is_refund, build_event, norm_header,
    )

CHANNEL = "square"
FEE_RATE = 0.029
FEE_FIXED = 0.30

HEADER_ALIASES: Dict[str, str] = {
    "Transaction ID": "order_id",
    "TransactionID": "order_id",
    "Payment ID": "order_id",
    "Receipt Number": "order_id",
    "Order": "order_id",
    "Order ID": "order_id",
    "Receipt": "order_id",
    "Date": "date",
    "Time": "date",
    "Timestamp": "date",
    "Created": "date",
    "Order Date": "date",
    "Time Zone": "date",
    "Description": "product",
    "Item": "product",
    "Product": "product",
    "Title": "product",
    "Listing": "product",
    "SKU": "product",
    "Details": "product",
    "Quantity": "qty",
    "Qty": "qty",
    "Units": "qty",
    "Gross Sales": "gmv",
    "Gross": "gmv",
    "Total Collected": "gmv",
    "Total": "gmv",
    "Amount": "gmv",
    "Net Sales": "gmv",
    "Order Total": "gmv",
    "Sales": "gmv",
    "Unit Price": "gmv_unit",
    "Price": "gmv_unit",
    "Fee": "fees",
    "Fees": "fees",
    "Square Fee": "fees",
    "Processing Fee": "fees",
    "Commission": "fees",
    "Tax": "fees",
    "Tip": "fees",
    "Discounts": "fees",
    "Shipping": "shipping",
    "Postage": "shipping",
    "Delivery": "shipping",
    "Customer": "customer",
    "Buyer": "customer",
    "Card": "customer",
    "Recipient": "customer",
    "Email": "customer",
    "Status": "status",
    "State": "status",
    "Type": "type",
    "Source": "type",
    "Tender": "type",
    "Payment Method": "type",
    "Currency": "currency",
    "Net Total": "fees",
    "Gift Card Sales": "type",
    "Partial Refunds": "type",
}


def _estimate_fee(gmv_abs: float) -> float:
    if gmv_abs <= 0:
        return 0.0
    return round(gmv_abs * FEE_RATE + FEE_FIXED, 2)


def parse_rows(rows: List[Dict[str, Any]], source_file: str = "square.csv") -> List[Dict[str, Any]]:
    try:
        if not rows:
            return []
        fieldnames = list(rows[0].keys())
        fmap = canonicalize_headers(fieldnames, HEADER_ALIASES)
        if not has_known_fields(fmap):
            return []
        events: List[Dict[str, Any]] = []
        for idx, row in enumerate(rows, 2):
            try:
                norm: Dict[str, str] = {}
                for raw, val in row.items():
                    canon = fmap.get(str(raw), norm_header(str(raw)))
                    s = "" if val is None else str(val).strip()
                    if canon == "gmv" and canon in norm and norm[canon]:
                        try:
                            if parse_money_abs(s) > parse_money_abs(norm[canon]):
                                norm[canon] = s
                        except Exception:
                            pass
                    elif canon not in norm or not norm[canon]:
                        norm[canon] = s
                order_id = (norm.get("order_id") or "").strip()
                date_raw = norm.get("date") or ""
                product = (norm.get("product") or norm.get("item") or norm.get("sku") or "").strip()
                qty_raw = norm.get("qty") or ""
                gmv_raw = (norm.get("gmv") or norm.get("amount") or norm.get("total")
                           or norm.get("gross") or "")
                unit_raw = norm.get("gmv_unit") or norm.get("price") or ""
                fees_raw = norm.get("fees") or ""
                ship_raw = norm.get("shipping") or ""
                customer = (norm.get("customer") or "").strip()
                status_raw = norm.get("status") or ""
                # Square refund often in Type/Source columns mapped to type
                type_raw = norm.get("type") or ""
                currency_raw = norm.get("currency") or ""
                qty = parse_qty(qty_raw, default=1)
                gmv_abs = parse_money_abs(gmv_raw)
                if gmv_abs == 0 and unit_raw:
                    try:
                        gmv_abs = round(parse_money_abs(unit_raw) * abs(qty if qty != 0 else 1), 2)
                    except Exception:
                        pass
                if gmv_abs < 0.005:
                    continue
                refund = is_refund(type_raw, status_raw, qty_raw, gmv_raw, qty)
                fees_abs = parse_money_abs(fees_raw)
                # Square Net Total col is net payout, not fee; if fees col was Net Total,
                # parse would give net value as fee — guard: if fees_abs >= gmv_abs, re-estimate
                if fees_abs >= gmv_abs and gmv_abs > 0:
                    fees_abs = _estimate_fee(gmv_abs)
                elif fees_abs == 0:
                    fees_abs = _estimate_fee(gmv_abs)
                ship_abs = parse_money_abs(ship_raw)
                currency = detect_currency_code(gmv_raw, fees_raw, currency_raw,
                                                " ".join(str(v or "") for v in row.values()))
                ts = parse_date(date_raw)
                if not product or product.lower() in ("unknown", "none", ""):
                    product = f"order:{order_id or idx}"
                if refund:
                    qty = -abs(qty if qty != 0 else 1)
                    gmv = -abs(gmv_abs)
                    signal = "order_refund"
                else:
                    qty = abs(qty if qty != 0 else 1)
                    gmv = abs(gmv_abs)
                    signal = "order_gmv"
                events.append(build_event(CHANNEL, source_file, idx, ts, order_id,
                                          product, qty, gmv, fees_abs, ship_abs,
                                          customer, status_raw, signal, currency))
            except Exception:
                continue
        return events
    except Exception:
        return []
