# 06 — Guía de ajuste de umbrales

Todos los números de Seller OS salen de una tabla: `SCENARIO_THRESHOLDS` en
`src/omni_one/packs/seller_scenarios.py` + `COVER_DAYS`/`STOCKOUT_DAYS` en
`src/omni_one/packs/seller_close.py`. Ajusta por tienda y cita el cambio en el cierre.

| Control | Defecto | Sube cuando | Baja cuando |
|---|---|---|---|
| `stockout_days` | 5.0 | proveedor tarda > 7 días | digital / bajo demanda |
| `COVER_DAYS` | 14 | proveedor lento, superventas | caja ajustada, poco almacén |
| `fee_creep_pct` | 12.0 | mucho Amazon (15% normal) | solo Shopify (~3%) |
| `shipping_loss_pct` | 20.0 | envío gratis desde $X | productos ligeros |
| `margin_low_pct` | 10.0 | hecho a mano (meta 50%+) | reventa de volumen |
| `dm_backlog_count` | 3 | una persona, fines de semana | equipo, SLA 2h |
| `price_mismatch_pct` | 5.0 | varias monedas | misma moneda multicanal |
| `dead_stock_min_qty` | 5 | almacenaje caro | accesorios pequeños |

Procedimiento: cambia UN control → `omni-one close --folder <tienda> --out /tmp/close_despues` →
compara `reorder.csv` + `close.csv` → conserva si `money_at_risk` baja sin spam de pedidos.
Registra el control + motivo en `close.json` para el contador.
Nunca ajustes para ocultar una fuga — las comisiones son hechos, el precio es la palanca.
