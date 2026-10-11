"""WooCommerce connector -> canonical events."""
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

CHANNEL = "woocommerce"
FEE_RATE = 0.029
FEE_FIXED = 0.30

HEADER_ALIASES: Dict[str, str] = {
    "Order ID": "order_id",
    "Order Number": "order_id",
    "Order #": "order_id",
    "ID": "order_id",
    "Receipt": "order_id",
    "Order": "order_id",
    "Order Date": "date",
    "Date": "date",
    "Created": "date",
    "Timestamp": "date",
    "Paid Date": "date",
    "Product": "product",
    "Product Name": "product",
    "Item": "product",
    "Line Item": "product",
    "Title": "product",
    "Description": "product",
    "SKU": "product",
    "Listing": "product",
    "Quantity": "qty",
    "Qty": "qty",
    "Units": "qty",
    "Item Qty": "qty",
    "Item Total": "gmv",
    "Order Total": "gmv",
    "Total": "gmv",
    "Gross": "gmv",
    "Amount": "gmv",
    "Sales": "gmv",
    "Net Total": "gmv",
    "Item Cost": "gmv_unit",
    "Unit Price": "gmv_unit",
    "Price": "gmv_unit",
    "Fee Total": "fees",
    "Fees": "fees",
    "Fee": "fees",
    "Transaction Fee": "fees",
    "Commission": "fees",
    "Tax Total": "fees",
    "Shipping Total": "shipping",
    "Shipping": "shipping",
    "Postage": "shipping",
    "Delivery": "shipping",
    "Shipping Method": "shipping",
    "Customer": "customer",
    "Buyer": "customer",
    "Email": "customer",
    "Recipient": "customer",
    "Billing Email": "customer",
    "Order Status": "status",
    "Status": "status",
    "State": "status",
    "Fulfillment": "status",
    "Payment Method": "type",
    "Type": "type",
    "Coupon": "type",
    "Currency": "currency",
    "Refund": "type",
}


def _estimate_fee(gmv_abs: float) -> float:
    if gmv_abs <= 0:
        return 0.0
    return round(gmv_abs * FEE_RATE + FEE_FIXED, 2)


def parse_rows(rows: List[Dict[str, Any]], source_file: str = "woocommerce.csv") -> List[Dict[str, Any]]:
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
