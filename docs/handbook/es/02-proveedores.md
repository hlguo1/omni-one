# Manual de proveedores — POs, renegociación y control de COGS

> Los proveedores son tu segundo mayor coste después de las comisiones de canal, y el único
> con el que puedes negociar con un humano. Este manual convierte el
> `reorder.csv` + `po.txt` del cierre diario en órdenes de compra que llegan a tiempo, a un
> precio que puedes demostrar.

## 1. Cómo leer `reorder.csv`

```
product,on_hand,sold_7d,daily_velocity,days_left,reorder_qty_14d,supplier,urgency,citation
Tote Bag Handmade,2,6,0.86,2.3,10,Acme Textiles,ORDER TODAY,[inventory.csv:2]
```

| Columna | Definición |
|---|---|
| `on_hand` | Unidades en `inventory.csv` ahora mismo |
| `sold_7d` | Unidades vendidas en los últimos 7 días de archivos de pedidos |
| `daily_velocity` | `sold_7d / 7` |
| `days_left` | `on_hand / daily_velocity` (999 = sin ventas) |
| `reorder_qty_14d` | `ceil(velocidad × 14 − on_hand)`, mínimo 0 |
| `urgency` | `ORDER TODAY` (< 3d) · `this week` (< 5d) · `watch` |

**Política de cobertura:** 14 días. ¿Por qué 14? Cubre el plazo medio
de proveedor pequeño (7–10 días) más un fin de semana de sobreventa, sin inmovilizar caja en
stock muerto. Si tu proveedor envía en 3 días, baja a 7 (edita `COVER_DAYS`
en `seller_close.py`). Si envía desde el extranjero (20+ días), sube a 30 —
y busca un proveedor de respaldo (sección 5).

## 2. Guiones de PO (copia-pega, luego rellena los corchetes)

### 2a. Reposición estándar (generada automáticamente como `po.txt`)

```
Subject: Reorder request — [SUPPLIER]

¡Hola [NAME]!

Por favor envía lo siguiente para [YOUR SHOP]:
  - Tote Bag Handmade: 10 unidades (tengo 2, 2.3d restantes) [[inventory.csv:2]]

Por favor confirma precio + ETA. Los números de la última factura están citados arriba desde nuestros registros.

¡Gracias!
[YOUR SHOP]
```

Reglas: cita siempre tu última factura, pide siempre **precio + ETA en el
mismo email** (una ida y vuelta, no dos), indica siempre la cantidad como
número, nunca "algo más".

### 2b. Primer pedido con un proveedor nuevo

```
Subject: First order + samples — [YOUR SHOP]

¡Hola [NAME]! Llevo [SHOP], [X] pedidos/mes en [CHANNEL].
Me gustaría empezar con:
  - [PRODUCT]: [QTY] unidades a [TARGET UNIT PRICE]
Preguntas:
  1. ¿Precio unitario a [QTY] y a [2×QTY]?
  2. ¿Plazo a [CITY]? ¿Política de defectos/devoluciones?
  3. ¿Puedes enviar 1 muestra? Pago yo + envío.
Si las muestras pasan, la primera PO sale esta semana.
¡Gracias! [YOU]
```

### 2c. Reclamar una entrega tardía (7+ días, sin tracking)

```
Subject: Checking ETA — PO of [DATE] ([QTY]× [PRODUCT])

¡Hola [NAME]! Nuestra PO del [DATE] no ha llegado y estamos a [N] días de
rotura ([citation]). ¿Puedes confirmar el tracking hoy?
Si no puede enviar antes del [DATE], dímelo ahora para dividir el pedido.
¡Gracias! [YOU]
```

### 2d. Lote defectuoso

```
Subject: Defect batch — [PRODUCT], [N] units ([DATE] delivery)

¡Hola [NAME]! [N] de [QTY] unidades del lote del [DATE] tienen [DEFECT].
Fotos adjuntas. Según tu política de devoluciones, me gustaría [reemplazo / reembolso
de $X]. Necesito los reemplazos antes del [DATE] para evitar rotura.
¿Puedes confirmar hoy? ¡Gracias! [YOU]
```

## 3. Umbrales de renegociación

Renegocia (o vuelve a cotizar) cuando salte **cualquiera** de estos — revisa mensualmente:

| # | Umbral | Cómo detectarlo | Acción |
|---|---|---|---|
| 1 | Coste unitario sube > 5% sin aviso | Nueva línea de factura vs biblia de COGS (§4) | Email en 48h citando precio antiguo + línea de factura |
| 2 | COGS > 45% del retail en cualquier top-3 SKU | `close.csv` cogs vs GMV por producto | Sube retail $1–2 *o* renegocia *o* re-abastece |
| 3 | Plazo se retrasa 2× en un trimestre | Tu registro de POs (fecha enviada vs llegada) | Doble fuente para ese SKU (sección 5) |
| 4 | Tasa de defectos > 3% de un lote | Reseñas/DMs que citan daños + tu conteo QC | Email de defectos (§2d) + 5% descuento o reemplazos gratis |
| 5 | Proveedor sin respuesta > 72h en un ORDER TODAY | Tu carpeta de enviados | Escala a teléfono; inicia prueba con proveedor respaldo |
| 6 | Margen real combinado < 10% durante 2 semanas | Titulares del cierre | Revisión total de costes: comisiones (§4 rutina matutina), COGS, envío — en ese orden |

### Guion de renegociación

```
Subject: Price review — [PRODUCT] ([QTY]/month run-rate)

¡Hola [NAME]! Hemos pedido [QTY] unidades/mes durante [N] meses (última:
[invoice citation]). Tu última cotización es $[NEW] vs nuestro coste
de trabajo $[OLD] (factura [citation]).
Quiero quedarme contigo — ¿puedes llegar a $[TARGET]? Puedo comprometerme a
[QTY] unidades/mes por 3 meses + pagar en [X] días.
Si no, lo entiendo — tendré que dividir volumen en otro lado.
¡Gracias! [YOU]
```

Mecánicas que funcionan mejor que rogar: **compromete volumen** (aunque sea poco),
**paga más rápido** (7 días vence a 30), **pide predecible** (mismo día mensual).
Los proveedores descuentan fiabilidad, no simpatía.

## 4. Control de COGS (la biblia)

Guarda un archivo — papel vale — con una fila por SKU:

```
SKU     Product            Supplier      Unit $  Since       Lead time  Notes
TB001   Tote Bag Handmade  Acme Textiles 4.00    2024-09-10   8d        canvas+strap
CM002   Ceramic Mug        Clay Co       6.10    2024-09-10   6d
```

Cómo calcula el COGS el cierre (para que puedas auditarlo):

1. Líneas de factura `.txt` de proveedor con forma `NAME QTY x UNIT TOTAL`
   (p. ej. `Tote Bag Canvas 50 x 4.00 200.00`) construyen un catálogo por material.
2. Cada producto de pedido coincide por difuso con el catálogo → COGS `unit × qty`.
3. Sin coincidencia → 30% del GMV de esa fila (heurística documentada).
4. Sin facturas → 25% del total de la factura más pequeña (último recurso).

**Tu trabajo:** haz que el paso 2 siempre acierte — mantén palabras de factura que solapen
tus títulos de anuncio (`Tote`, `Mug`, `Print`, `Scarf`). Una palabra compartida basta.
Revisa `close.json → kpis.cogs` semanalmente: si salta sin cambio de precio,
una línea de factura dejó de coincidir.

### Higiene de facturas
- Un `.txt` por entrega: nombre de proveedor, una línea `QTY x UNIT TOTAL` por
  material, `Shipping`, `Total $X`. Las fotos valen (OCR), pero el texto
  es exacto.
- Nunca guardes foto y copia manual con números distintos —
  el cierre deduplica archivos *idénticos*, no *conflictivos*.
- Patrón de nombre: `supplier_invoice_YYYY-MM-DD.txt` (la fecha los mantiene ordenables).

## 5. Doble fuente (la póliza de la persona sola)

Solo para tu #1 más vendido:
- [ ] Identifica proveedor respaldo (mayorista Etsy, muestra Alibaba, maker local).
- [ ] Pedido de prueba: cantidad mínima, anota unitario + plazo + conteo de defectos.
- [ ] Regla de reparto: principal 70% / respaldo 30% cuando el respaldo pase 2 entregas limpias.
- [ ] Si el plazo del principal supera `days_left` en `reorder.csv`, invierte el reparto ya.

Coste: un pedido de muestra extra por trimestre. Premio: nunca pierdes tu mejor
vendedor por el retraso de otro.

## 6. Tarjeta mensual de proveedores (10 min)

| Proveedor | Pedidos | % a tiempo | % defectos | Δ unitario | Veredicto |
|---|---|---|---|---|---|
| Acme Textiles | 3 | 100 | 0 | +0% | mantener |
| Clay Co | 2 | 50 | 5% | +6% | renegociar / probar respaldo |

Descarta cualquier proveedor con < 70% a tiempo o > 5% defectos dos meses seguidos.
Tu tienda es demasiado pequeña para subvencionar el caos ajeno.
