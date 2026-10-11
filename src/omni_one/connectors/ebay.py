"""eBay connector -> canonical events."""
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

CHANNEL = "ebay"
FEE_RATE = 0.1325
FEE_FIXED = 0.30

HEADER_ALIASES: Dict[str, str] = {
    "Order number": "order_id",
    "Order Number": "order_id",
    "Order ID": "order_id",
    "eBay Order ID": "order_id",
    "Receipt": "order_id",
    "Order": "order_id",
    "Sale date": "date",
    "Sale Date": "date",
    "Order Date": "date",
    "Date": "date",
    "Timestamp": "date",
    "Created": "date",
    "Item title": "product",
    "Item Title": "product",
    "Product": "product",
    "Title": "product",
    "Listing": "product",
    "Description": "product",
    "Item": "product",
    "SKU": "product",
    "Quantity": "qty",
    "Qty": "qty",
    "Units": "qty",
    "Total price": "gmv",
    "Total Price": "gmv",
    "Total": "gmv",
    "Order Total": "gmv",
    "Sold price": "gmv_unit",
    "Sold Price": "gmv_unit",
    "Sale Price": "gmv_unit",
    "Price": "gmv_unit",
    "Gross": "gmv",
    "Amount": "gmv",
    "Final value fee": "fees",
    "Final Value Fee": "fees",
    "Transaction fee": "fees",
    "Fees": "fees",
    "Fee": "fees",
    "Commission": "fees",
    "eBay Fee": "fees",
    "Shipping": "shipping",
    "Postage": "shipping",
    "Delivery": "shipping",
    "Sales tax": "shipping",
    "Sales Tax": "shipping",
    "Buyer": "customer",
    "Customer": "customer",
    "Recipient": "customer",
    "Buyer Username": "customer",
    "Order status": "status",
    "Order Status": "status",
    "Status": "status",
    "State": "status",
    "Type": "type",
    "Payment method": "type",
    "Payment Method": "type",
    "Currency": "currency",
}


def _estimate_fee(gmv_abs: float) -> float:
    if gmv_abs <= 0:
        return 0.0
    return round(gmv_abs * FEE_RATE + FEE_FIXED, 2)


def parse_rows(rows: List[Dict[str, Any]], source_file: str = "ebay.csv") -> List[Dict[str, Any]]:
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
                # eBay: prefer Total price as gmv (includes order total)
                gmv_raw = (norm.get("gmv") or norm.get("amount") or norm.get("total")
                           or norm.get("gross") or "")
                unit_raw = norm.get("gmv_unit") or norm.get("price") or ""
                fees_raw = norm.get("fees") or ""
                ship_raw = norm.get("shipping") or ""
                customer = (norm.get("customer") or "").strip()
                status_raw = norm.get("status") or ""
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
                if fees_abs == 0:
                    fees_abs = _estimate_fee(gmv_abs)
                ship_abs = parse_money_abs(ship_raw)
                currency = detect_currency_code(gmv_raw, fees_raw, ship_raw, currency_raw,
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
