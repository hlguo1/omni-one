# Cierre diario — el ritual de 5 minutos que tu tienda corre cada mañana

> Los vendedores no viven en paneles. **Cierran el día**: dinero dentro, clientes enfadados respondidos,
> estanterías repuestas, fugas tapadas, contador con su archivo. El Cierre diario de Omni-One es ese ritual
> en un comando — offline, gratis ($0), privado, cada número citado `file:line`.

## El comando

```bash
omni-one close --folder /tmp/my_shop --out ./close_2026-10-11 --shop "Maya's Handmade"
# -> close.json + close.csv + reorder.csv + replies.txt + po.txt
```

Qué obtienes (en disco):

- `close.json` — todo, para API/MCP/automatización.
- `close.csv` — KPIs + acciones + fugas, listo para contador/hojas.
- `reorder.csv` — listo para proveedor: producto, existencias, días, cantidad 14d, cita.
- `replies.txt` — borradores copia-pega + email de PO en un imprimible.
- `po.txt` — envíalo tal cual al proveedor.

## La rutina de mañana (5 min)

| Min | You do | Close gives you |
|-----|--------|-----------------|
| 0–1 | Read the headline | `Profit $169.09 (61.7%) · $102.75 at risk in 3 angry messages · 1 reorder TODAY · 0 leaks` |
| 1–3 | Copy-paste replies | `replies.txt`: 3 drafts with customer name, issue, order citation — send in IG/Etsy/Amazon |
| 3–4 | Send the PO | `po.txt`: `Subject: Reorder — Acme Textiles: Tote x10 (2 left, 2.3d supply) [inventory.csv:2]` |
| 4–5 | File + fix | `close.csv` → accountant/sheets; fix 1 listing from `listing_fixes` |

En español, minuto a minuto:

- 0–1: lee el titular en voz alta. Si dice `1 reorder TODAY`, hoy hay PO. Si dice `3 angry messages`, hoy hay respuestas antes que café.
- 1–3: abre `replies.txt`, personaliza una frase por borrador, envía en IG/Etsy/Amazon. P0 (< 2h) sin excepción.
- 3–4: copia `po.txt`, rellena huecos, envíalo. Pide tracking + envío parcial si hay algo en stock.
- 4–5: archiva `close.csv` (contador/hojas) y corrige 1 ficha de `listing_fixes`.

## Qué calcula (determinista, sin LLM para números)

- **True profit, not GMV**: GMV − fees − shipping − COGS (COGS from supplier invoices via OCR/photo or CSV; per-unit catalog; 30% heuristic fallback). Golden demo: GMV $274.00 → profit **$169.09**.
- **Money at risk**: `unanswered complaints × AOV`. Each ignored "where is my order" ≈ one refund + one 1-star. Demo: 3 messages × $34.25 AOV ≈ **$102.75 at risk** — that number gets owners out of bed.
- **Reorder sheet**: `daily_velocity = sold_7d/7`, `days_left = on_hand/velocity`, `reorder_qty = ceil(velocity×14 − on_hand)`. Tote demo: 2 left, 6 sold/7d → **2.3d left → ORDER TODAY x10**. Urgency: `<3d ORDER TODAY`, `<5d this week`.
- **Reply drafts**: deterministic templates (no hallucination, no cost) grounded in `[file:line]`: apology + order pull + 2h fix promise + reship/refund choice. Review variant for public replies.
- **Money leaks with $**: fee creep (fees/GMV ≥12% → $ + channel comparison), shipping loss per order (≥20%), margin dip (<10%), COGS spike. Each with dollar + evidence.
- **Listing fixes**: LISTING_GAP (sales, zero reviews → UGC ask), REVIEW_CRISIS (public reply), PRICE_MISMATCH (align channels), WORST_SELLER (clearance).

Traducción de la lógica (solo prosa, fórmulas intactas):

- Beneficio real = GMV − comisiones − envío − COGS (COGS por OCR/foto o CSV; catálogo unitario; heurística 30% si falta).
- Dinero en riesgo = reclamaciones sin responder × ticket medio (3 × $34.25 ≈ $102.75).
- Hoja de reposición: velocidad = vendidos_7d/7; días = existencias/velocidad; cantidad = ceil(velocidad×14 − existencias).
- Borradores deterministas con `[file:line]`: disculpa + pedido + promesa 2h + opción reenvío/reembolso.
- Fugas con $ y evidencia; fichas con 4 jugadas (UGC, respuesta pública, alinear precio, liquidar).

## Entradas: tu desorden, tal cual

Drop anything in the folder — parsers auto-detect, no renaming:
`shopify_orders.csv` / `etsy_settlement.csv` / `amazon_*.csv` (any headers), `inventory.csv`
(with `supplier` column kept), `reviews.csv`, `instagram_dm.txt` / `tiktok_dm.json`,
`supplier_invoice.jpg/png/pdf/txt` (Tesseract OCR + sidecar `.jpg.txt` dedup via content hash).

Consejos en español:

- Nombra `shopify_*`, `etsy_*`, `amazon_*` para clavar el canal (Etsy ≈ 6.5%+$0.20 · Shopify ≈ 2.9%+$0.30 · Amazon ≈ 15%).
- Mantén la columna `supplier` en `inventory.csv` (alimenta `po.txt`).
- Exporta DMs como `.txt`/`.json` (las capturas no se leen).
- Si un CSV usa `;` o trae BOM, el Sniffer lo soporta (`UTF-8-SIG`).

## Salidas: artefactos que ya usas

- `close.csv` — accountant/sheets-ready KPIs + actions + leaks
- `reorder.csv` — supplier-ready: product, on_hand, days_left, qty_14d, supplier, citation
- `replies.txt` — copy-paste drafts + PO email in one printable file
- `po.txt` — send as-is to supplier
- `close.json` — everything, for API/MCP/automation

## Interfaces

```bash
omni-one close --demo --out ./close_today        # CLI
omni-one close --folder /tmp/my_shop --out ./close_2026-10-11
POST /api/v1/seller/close {"demo":true}          # API
GET  /api/v1/seller/close.csv?demo=true          # CSV download
{"tool":"seller_close","args":{"demo":true}}     # MCP (Claude/Cursor)
from omni_one.client import OmniOneClient        # SDK
OmniOneClient.local().close(demo=True)["headline"]
```

## Bucle de hábito (por qué engancha)

Day 1: folder drop → close bundle → 1 refund saved ≈ pays for the year (it's $0).
Day 7: supplier catalog + velocity learned → reorder qty gets smarter, PO one-click.
Day 30: `money_at_risk → $0` streak + margin trend → the close becomes the shop's P&L.

En español:

- Día 1: suelta la carpeta → paquete → 1 reembolso salvado ≈ paga el año (es $0).
- Día 7: catálogo + velocidad aprendidos → cantidad más lista, PO en un clic.
- Día 30: racha `money_at_risk → $0` + tendencia de margen → el cierre es tu PyG.

Roadmap: scheduled 7am close (`cron` + email), multi-shop compare, TikTok Shop parser,
Spanish/Chinese DM templates, photo stock-count (`on_hand` from shelf photo).

See: `src/omni_one/packs/seller_close.py`, `tests/unit/test_daily_close.py` (4 golden tests),
`examples/daily_close_demo.py`, `docs/SCENARIOS.md` (12 detectors feeding the close).
