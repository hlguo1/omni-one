"""PayPal connector -> canonical events."""
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

CHANNEL = "paypal"
FEE_RATE = 0.0349
FEE_FIXED = 0.49

HEADER_ALIASES: Dict[str, str] = {
    "Transaction ID": "order_id",
    "TransactionID": "order_id",
    "Invoice ID": "order_id",
    "Receipt": "order_id",
    "Order": "order_id",
    "Order ID": "order_id",
    "PayPal ID": "order_id",
    "Date": "date",
    "Time": "date",
    "Timestamp": "date",
    "Order Date": "date",
    "Payment Date": "date",
    "Created": "date",
    "Item Title": "product",
    "Item": "product",
    "Product": "product",
    "Title": "product",
    "Description": "product",
    "Item ID": "product",
    "Listing": "product",
    "SKU": "product",
    "Name": "customer",
    "Quantity": "qty",
    "Qty": "qty",
    "Units": "qty",
    "Gross": "gmv",
    "Amount": "gmv",
    "Total": "gmv",
    "Order Total": "gmv",
    "Sales": "gmv",
    "Payment Gross": "gmv",
    "Unit Price": "gmv_unit",
    "Price": "gmv_unit",
    "Fee": "fees",
    "Fees": "fees",
    "PayPal Fee": "fees",
    "Transaction Fee": "fees",
    "Commission": "fees",
    "Shipping": "shipping",
    "Postage": "shipping",
    "Delivery": "shipping",
    "Shipping Amount": "shipping",
    "From Email": "customer",
    "To Email": "customer",
    "Buyer": "customer",
    "Customer": "customer",
    "Recipient": "customer",
    "Email": "customer",
    "Status": "status",
    "State": "status",
    "Payment Status": "status",
    "Type": "type",
    "Payment Type": "type",
    "Payment Method": "type",
    "TimeZone": "type",
    "Time Zone": "type",
    "Currency": "currency",
    "Net": "fees",
}


def _estimate_fee(gmv_abs: float) -> float:
    if gmv_abs <= 0:
        return 0.0
    return round(gmv_abs * FEE_RATE + FEE_FIXED, 2)


def parse_rows(rows: List[Dict[str, Any]], source_file: str = "paypal.csv") -> List[Dict[str, Any]]:
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
                # PayPal Date+Time split: combine if Time col present but Date only has date
                product = (norm.get("product") or norm.get("item") or norm.get("sku") or "").strip()
                if not product:
                    # fallback: Name column is customer, not product; use order id
                    pass
                qty_raw = norm.get("qty") or ""
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
