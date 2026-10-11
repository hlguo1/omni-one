# Paquete del contador — diccionario de campos de `close.csv` + conciliación

> Tu contador no quiere un panel. Quiere totales que cuadren con el
> banco, con recibos. El cierre diario produce justo eso: `close.csv`
> (dinero), `reorder.csv` (intención de movimiento de inventario), `replies.txt` (rastro de
> evidencia de reembolsos). Esta página es el diccionario + la rutina mensual.

## 1. Diccionario de campos de `close.csv`

`close.csv` tiene cuatro secciones. La sección 1 es fila de título (`DAILY CLOSE,
<date>, <headline>`). Luego:

### Sección A — `metric,value` (la fila del libro)

| metric | Tipo | Definición | Archivos fuente |
|---|---|---|---|
| `gmv` | USD, 2dp | Valor bruto de mercancía: suma de totales de filas de pedido | `shopify_orders.csv`, `etsy_settlement.csv`, `amazon_payout.csv` |
| `fees` | USD, 2dp | Comisiones de canal: parseadas por fila, si no estimadas (Etsy 6.5%+$0.20 · Shopify 2.9%+$0.30 · Amazon 15% · otro 8%) | mismos archivos de pedidos |
| `shipping` | USD, 2dp | Envío pagado/cobrado por filas de pedido | mismos archivos de pedidos |
| `net` | USD, 2dp | `gmv − fees − shipping` | calculado |
| `cogs` | USD, 2dp | Coste de bienes vendidos, asignado por unidad desde facturas de proveedor (ver §3) | `supplier_invoice_*.txt` (+ sidecars OCR) |
| `true_profit` | USD, 2dp | `net − cogs`. **El** número. Dorado: tienda demo = $169.09 | calculado |
| `margin_pct` | %, 1dp | `true_profit / gmv × 100` (0 cuando gmv = 0) | calculado |
| `orders` | int | Filas de pedido ingeridas | archivos de pedidos |
| `aov` | USD, 2dp | `gmv / orders` (0 cuando no hay pedidos) | calculado |
| `best_seller` | objeto | `{product, qty, gmv}` top por unidades | calculado |
| `money_at_risk_usd` | USD, 2dp | `len(reply_queue) × aov` — exposición a reembolsos en quejas sin responder | DMs + reseñas |

**Invariante que tu contador puede comprobar:** `true_profit ≤ gmv` en cada fila,
siempre. (Los evals lo afirman por tienda; ver `evals/run.py`.) Si alguna vez falla,
los datos están corruptos — re-exporta los CSVs del canal.

### Sección B — `do_today_n,do_today` (acciones, no dinero)
Tres líneas: carga de respuestas, top reposición, top fuga. Informativo; no contabilizado.

### Sección C — bloque reorder
`product,on_hand,sold_7d,days_left,reorder_qty_14d,supplier,urgency,citation`
— la posición de stock a la hora del cierre. `reorder_qty_14d` es *intención de compra*,
no gasto contabilizado. Contabiliza el gasto cuando llega la factura del proveedor.

### Sección D — bloque de fugas
`leak,amount_usd,note,evidence` — subida de comisiones / pérdida de envío / caída de margen
con importes. `amount_usd` puede ir vacío para fugas unitarias (p. ej.
pérdida de envío por pedido); el `note` lleva el detalle.

## 2. `reorder.csv` + `replies.txt` + `po.txt`

| Archivo | Uso del contador |
|---|---|
| `reorder.csv` | Intención de inventario: qué pediste y por qué (cita por fila). Archiva con facturas de compra. |
| `replies.txt` | Rastro de evidencia para reembolsos/chargebacks: palabras del cliente + tu borrador + cita. Adjunta a transacciones disputadas. |
| `po.txt` | El email de PO tal como se envió. Archiva la confirmación del proveedor al lado. |
| `close.json` | Todo legible por máquina (KPIs, hoja de reorder completa, cola de respuestas, fugas, borrador PO). Guarda 12 meses. |

## 3. Cómo se calcula COGS (explícalo una vez, luego apunta aquí siempre)

1. Cada línea `.txt` de proveedor con forma `MATERIAL QTY x UNIT TOTAL`
   (ejemplo: `Tote Bag Canvas 50 x 4.00 200.00`) registra un coste unitario.
2. Cada fila de pedido coincide por difuso su producto con el catálogo; COGS += unit × qty.
3. Productos sin coincidencia caen a 30% del GMV de fila (implícito: COGS
   acaba en valores heurísticos redondos — investiga si un mes entero se ve así).
4. Sin facturas → 25% del total de la factura más pequeña (fallback de emergencia).

**Qué significa para contabilidad:** COGS en `close.csv` es *coste asignado
de vendidos para el mix de ese día*, apto para seguimiento de margen. Tu declaración
sigue usando facturas reales de compra (caja) — el cierre te cuenta
la historia de margen; la caja de facturas cuenta la historia fiscal. Deben
converger en pocos % mensual. Si no, una línea de proveedor dejó de
coincidir (deriva de nombres) — ver manual de proveedores §4.

## 4. Pasos de conciliación (mensual, 30 min)

**Necesitas:** los `close.csv` del mes, estados de payout del canal
(Shopify/Etsy/Amazon), extractos bancarios, facturas de proveedores.

- [ ] **Paso 1 — Suma los cierres.** Suma `gmv`, `fees`, `shipping`, `true_profit`
      en las filas Sección A del mes. (One-liner:
      `awk -F, '/^(gmv|fees|shipping|true_profit),/{s[$1]+=$2} END{for(k in s)print k,s[k]}' close_*/close.csv`.)
- [ ] **Paso 2 — Cuadra GMV con canales.** El GMV mensual debe coincidir con paneles
      dentro de ±2%. Brecha mayor → exportación faltante (una semana de pedidos
      nunca cayó en la carpeta) o archivo duplicado.
- [ ] **Paso 3 — Cuadra comisiones con payouts.** `fees` debe coincidir con
      (ventas canal − payout canal) dentro de ±3%. Etsy/Shopify estiman
      fórmulas cuando la exportación omite columnas de comisiones, así que ±3% es normal; ±10% significa
      que una columna se parsea mal — revisa nombres de cabecera.
- [ ] **Paso 4 — Cuadra beneficio con banco.** `true_profit − pagos a proveedores −
      reembolsos emitidos` debe seguir el delta de la cuenta del negocio dentro de $5–10
      (timing: payouts tardan 2–5 días; arrastra el lag explícito mes a mes).
- [ ] **Paso 5 — Auditoría de reembolsos.** Cuenta P0s de `replies.txt` vs reembolsos en el
      feed bancario. Cada reembolso necesita cita (mensaje del cliente). Huérfanos →
      actualiza el hábito de exportación de DMs.
- [ ] **Paso 6 — Firma.** Escribe una línea: `2024-09: GMV $X, profit $Y,
      reconciliado ±$Z — iniciales`. Guarda con los cierres del mes.

## 5. Discrepancias comunes y soluciones

| Discrepancia | Causa | Solución |
|---|---|---|
| GMV 5–15% bajo vs panel | Columna `price` de Etsy traía precio unitario, archivo usaba qty>1 (o viceversa) | Re-exporta con totales de línea; el generador escribe totales (ver `evals/generate.py`) |
| Comisiones ~0 en filas Shopify | Exportación omitió columna de comisiones → 2.9%+$0.30 estimado | Bien para ops; para fiscal, usa el payout statement, no la estimación |
| COGS salta mes a mes | Nueva redacción de proveedor rompió match difuso | Alinea una palabra entre factura y anuncio (manual proveedores §4) |
| Beneficio > GMV (nunca normal) | Fila corrupta (comisión negativa parseada como crédito) | Falla invariante de eval — encuentra la fila, corrige el CSV, re-ejecuta cierre |
| `money_at_risk` enorme | DMs viejos nunca limpiados de la carpeta | Archiva DMs atendidos mensualmente; la carpeta es *cola*, no archivo |
| Archivos punto-y-coma/BOM muestran 0 filas | Exportación Excel local | Soportado por el parser; verifica que abre como UTF-8 y el nombre contiene `order/shopify/etsy/amazon` |

## 6. Cierre de año (2 h, una vez)
- [ ] 12 líneas de firma mensual → totales para el asesor fiscal.
- [ ] Conteo de inventario (físico) vs suma de on-hands de `inventory.csv`; contabiliza merma.
- [ ] 1099s de proveedores (US) / equivalentes: total pagado por proveedor desde facturas.
- [ ] Archivo: `my_shop/` + todos los bundles `close_*` + PDFs de payout → dos sitios (USB + nube).
- [ ] No borres nada hasta declarar y pasar la ventana de reembolso (chargebacks: 120 días).
