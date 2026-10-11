# 07 — Guía de temporada de impuestos (para la reunión con el contador)

Trae: 12 × `close.json` + `close.csv` + `reorder.csv` + esta lista.

1. Cuadre de P&L: la suma de `true_profit` mensual == ganancia anual. Cada mes con margen < 0
   lleva una línea de causa desde `money_leaks` (fee_creep/shipping_loss/margin_dip/cogs_spike).
2. Prueba de COGS: facturas (`supplier_invoice*`) + OCR + costos unitarios del catálogo.
   Marca meses que usaron el 30% del GMV (sin factura).
3. Comisiones: pagado por canal vs tarifa (Shopify 2.9%+30c, Etsy 6.5%+20c, Amazon 15%,
   TikTok 5%+30c, eBay 13.25%+30c). Adjunta filas fee_creep como explicación.
4. Reembolsos: cuenta `REFUND_RISK` + `order_refund`; cuadra con débitos. Sin cita no pasó.
5. Inventario: `on_hand` × costo = stock del balance. La lista `DEAD_STOCK` respalda rebajas.
6. ZIP: `accountant_pack` → un ZIP por año, con manifiesto.

Líneas rojas: nada inventado (todo cita `file:line`), no edites CSV (regenera con
`omni-one close`), ningún mes faltante (cron `7am-close.cron`).
