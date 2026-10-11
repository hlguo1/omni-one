# Referencia rápida — Cierre diario Omni-One (chuleta de una página)

> Imprime esto. Pégalo en la pared junto a la mesa de empaquetado.
> Un comando ejecuta toda la mañana de la tienda: beneficio, reposiciones, respuestas, fugas.
> Cada número cita `file:line`. Sin cita, no hay acción.
> Fuentes: `docs/QUICKSTART.md`, `docs/API.md`, `docs/CLI.md`,
> `docs/DEPLOYMENT.md`, `docs/ROADMAP.md`, `docs/DAILY_CLOSE.md`,
> `docs/handbook/01-morning-routine.md`, `docs/handbook/05-incidents.md`,
> `docs/SCENARIOS.md`, `src/omni_one/packs/seller_scenarios.py`.

```bash
omni-one close --folder ~/my_shop --out ./close_today
# -> close.json + close.csv + reorder.csv + replies.txt + po.txt
```

Ejemplo de titular (la única línea que debes leer):

```
Profit $169.09 (61.7%) · $102.75 at risk in 3 angry messages · 1 reorder(s) TODAY · 0 leak(s) to plug
```

---

## 1. El ritual de 5 minutos (lista)

Copia esto en una tarjeta plastificada. Cronómetro en marcha. Nada de perderse en paneles.

- [ ] **0:00–0:30 — Ejecuta el cierre.**
  ```bash
  omni-one close --folder ~/my_shop --out ./close_today
  ```
  Lee el titular en voz alta. Si falla, ver §12 Solución de problemas.

- [ ] **0:30–2:00 — Respuestas primero.**
  Abre `replies.txt`. Copia-pega el borrador #1, personaliza una frase, envía.
  Repite mientras hierve el agua.
  Regla: **P0 (reembolso / no-ha-llegado / dañado) en menos de 2 horas, sin excepciones.**
  Ver `docs/handbook/03-reply-playbook.md`.

- [ ] **2:00–3:30 — Reposiciones.**
  Abre `reorder.csv`. Todo lo que sea `ORDER TODAY` → envía el borrador de `po.txt` hoy.
  Lo que sea `this week` → anótalo en la agenda.
  Ver `docs/handbook/02-supplier-playbook.md`.

- [ ] **3:30–4:30 — Una fuga.**
  Si `money_leaks` en `close.csv` no está vacío, haz la corrección más barata:
  normalmente subir un precio $1, o mover un SKU fuera del canal caro.
  Regístralo en una línea.

- [ ] **4:30–5:00 — Archiva.**
  Mueve las exportaciones del día a la carpeta de la tienda.
  Añade una línea a tu libro (ver `docs/handbook/04-accountant-pack.md`).

Lista diaria plastificada (versión corta):

- [ ] Cierre ejecutado, titular leído
- [ ] Todas las respuestas P0 enviadas < 2h
- [ ] POs `ORDER TODAY` enviadas
- [ ] Una fuga tocada
- [ ] Archivos archivados

Semanal (viernes, 20 min):

- [ ] 7 cierres conciliados, GMV vs paneles ±2%
- [ ] ETAs de proveedores reclamados (pedido hace > 7 días sin seguimiento)
- [ ] Stock muerto listado (0 ventas + 5+ unidades → borrador de liquidación)
- [ ] Precios revisados frente a cambios de comisiones
- [ ] Copia de seguridad: copiar `~/my_shop` a USB / segundo equipo

Mensual (primer lunes, 1 h):

- [ ] `close.csv` del mes → paquete del contador
- [ ] Ficha de proveedores actualizada (precio, ETA, tasa de defectos)
- [ ] Decisión del peor vendedor: eliminar, empaquetar o liquidar
- [ ] Suelo de margen: ¿margen real combinado ≥ 10%?

---

## 2. Instalación + primera ejecución (60 segundos, $0)

```bash
git clone https://github.com/garyguo123456789/omni-one.git && cd omni-one
pip install -r requirements-seller.txt && pip install -e .
omni-one doctor                                        # deps + pipeline smoke
omni-one close --demo --out ./close_today             # THE ritual: profit + reorders + replies
cat ./close_today/replies.txt                         # copy-paste a draft, send the PO
```

Tu tienda:

```bash
mkdir -p /tmp/my_shop
cp ~/Downloads/*orders*.csv ~/Downloads/inventory.csv /tmp/my_shop/
cp examples/my_shop_template/*.csv /tmp/my_shop/   # fill blanks if needed
omni-one close --folder /tmp/my_shop --out ./close_2026-10-11 --shop "Maya's Handmade"
```

Servidor + SDK + bot:

```bash
omni-one serve --port 5003 &                            # docs at /api/docs
PYTHONPATH=src python3 examples/sdk_demo.py
PYTHONPATH=src python3 examples/daily_close_demo.py
```

Claude/Cursor MCP:

```bash
python3 -m omni_one.mcp_server
```

Herramientas MCP: `seller_close`, `seller_briefing`, `seller_scenarios`,
`seller_operations`, `pipeline_analyze`, `vision_analyze`.

---

## 3. Todos los comandos CLI

Ejecuta como `omni-one <cmd>` (tras `pip install -e .`)
o `PYTHONPATH=src python3 -m omni_one.cli <cmd>`.
`make demo|close|test|e2e|serve|docker|lint|doctor` envuelve lo mismo.

| Comando | Qué hace | Invocación típica |
|---|---|---|
| `omni-one doctor` | entorno + dependencias + humo del pipeline | `omni-one doctor` |
| `omni-one demo` | briefing demo del vendedor | `omni-one demo` |
| `omni-one briefing --demo --json b.json` | briefing; `--folder /p` para tienda real | `omni-one briefing --folder ~/my_shop` |
| `omni-one scenarios --demo` | 12 escenarios ordenados | `omni-one scenarios --demo` |
| `omni-one operations` | bucle completo ontología→taller→AIP→auditoría | `omni-one operations --demo` |
| `omni-one close --demo --out ./close_today` | **paquete del Cierre diario** (json/csv/reorder/replies/po) | `omni-one close --folder ~/my_shop --out ./close_today` |
| `omni-one export --demo --out briefing.csv` | CSV del briefing | `omni-one export --demo --out briefing.csv` |
| `omni-one serve --port 5003` | servidor API | `omni-one serve --port 5003` |
| `omni-one evaluate --n 500` | arnés de evaluación | `omni-one evaluate --n 500` |

Opciones que usarás de verdad:

| Opción | Significado | Ejemplo |
|---|---|---|
| `--demo` | usa la tienda demo dorada incluida | `omni-one close --demo --out ./close_today` |
| `--folder /path` | carpeta de tu tienda real | `omni-one close --folder /tmp/my_shop --out ./close_2026-10-11` |
| `--out ./dir` | dónde escribir el paquete | `omni-one close --demo --out ./close_today` |
| `--shop "Name"` | nombre visible de la tienda en la cabecera | `omni-one close --folder /tmp/my_shop --out ./close_2026-10-11 --shop "Maya's Handmade"` |
| `--json b.json` | escribe el briefing JSON a un archivo | `omni-one briefing --demo --json b.json` |
| `--port 5003` | puerto de la API | `omni-one serve --port 5003` |
| `--n 500` | número de registros de evaluación | `omni-one evaluate --n 500` |

Cron: cierre diario 7am:

```cron
0 7 * * * cd /path/to/omni-one && PYTHONPATH=src python3 -m omni_one.cli close --folder ./data/inbox --out ./close_$(date +\%F) >> ./close_cron.log 2>&1
```

Docker (servicio único):

```bash
docker build -t omni-one:latest .
docker compose up -d && curl -sf http://localhost:5003/health
```

Endurecimiento en producción:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"  # twice
ENVIRONMENT=production VALID_API_KEYS=<32+> SECRET_KEY=<32+> docker compose up -d
```

---

## 4. Todas las rutas API (18)

Base: `http://localhost:5003`. Docs: `/api/docs`.
Salud: `/health`, `/readiness`, `/status`, `/ping`.
Métricas: `/metrics` (Prometheus).

### 4a. Cierre diario (héroe) — 3 rutas

| # | Método + ruta | Cuerpo / query | Devuelve |
|---|---|---|---|
| 1 | `POST /api/v1/seller/close` | `{"demo":true}` o `{"folder":"/path","shop":"Maya's"}` | paquete del cierre (titular, kpis+money_at_risk, do_today, reorder_sheet, reply_queue+drafts, leaks, listing_fixes, po_draft). Contador `closes_total`. |
| 2 | `GET /api/v1/seller/close.csv?demo=true` | `?demo=true` o `?folder=/path` | descarga CSV para el contador |
| 3 | `GET /api/v1/seller/export.csv?demo=true` | `?demo=true` | CSV del briefing |

### 4b. Seller OS — 5 rutas

| # | Método + ruta | Cuerpo / query | Devuelve |
|---|---|---|---|
| 4 | `POST /api/v1/seller/briefing` | `{"demo":true}` o `{"folder":"/path"}` | beneficio real / rotura de stock / alertas / borrador / gráfico |
| 5 | `POST /api/v1/seller/operations` | `{"demo":true}` | bucle completo briefing→ontología→taller→AIP→auditoría |
| 6 | `GET /api/v1/seller/scenarios` | — | registro de 12 escenarios + umbrales |
| 7 | `POST /api/v1/seller/scenarios/run` | `{"demo":true}` | decisiones idempotentes ordenadas + taller + auditoría |
| 8 | `POST /api/v1/seller/photo` (multipart) | campo de archivo de imagen | factura de proveedor / foto de producto → OCR+gráfico+pipeline |

### 4c. Motor — 7 rutas

| # | Método + ruta | Cuerpo / query | Devuelve |
|---|---|---|---|
| 9 | `POST /api/v1/analyze` | `{"records":[...]}` | pipeline de 4 capas + evidencia + coste |
| 10 | `POST /api/v1/synthesize` | cuerpo de síntesis | síntesis LLM con compuerta + caché + citas |
| 11 | `POST /api/v1/vision/analyze` (multipart) | campo de archivo de imagen | OCR+gráfico gratis |
| 12 | `GET /api/v1/vision/demo` | — | resultado demo de visión |
| 13 | `GET /api/v1/metrics` | — | métricas vivas de evaluación de 200 registros |
| 14 | `GET /api/v1/models` | — | catálogo de modelos |
| 15 | `POST /api/v1/micro/briefing` | cuerpo micro-negocio | laboratorio: micro briefing |

### 4d. Labs + admin — 3 rutas

| # | Método + ruta | Cuerpo / query | Devuelve |
|---|---|---|---|
| 16 | `POST /api/v1/revenue/health` | cuerpo de ingresos | laboratorio: salud de ingresos |
| 17 | `GET /api/v1/admin/services` | cabecera `X-API-Key` / `Bearer`, cerrado por defecto | estado de servicios (en prod: requiere clave) |
| 18 | `POST /api/v1/admin/clear-cache` | cabecera `X-API-Key` / `Bearer`, cerrado por defecto | limpia caché (en prod: requiere clave) |

Notas:

- Todos los números del vendedor citan `file:line`. LLM simulado por defecto (`SELLER_LLM=mock`, `$0`).
- Las claves demo (`demo-key` / `test-key`) se rechazan en producción; `/admin/*` necesita clave.
- Subidas limitadas (5MB, con tipo verificado, 60/min); carpetas enjauladas en `ALLOWED_ROOT`.
- La auditoría `verify()` demuestra inviolabilidad. Ver `SECURITY.md`.
- Monitorización: raspa `GET /metrics` (contadores de briefings / escenarios / cierres / visión + `omni_one_up`).
- SDK:
  ```python
  from omni_one.client import OmniOneClient
  OmniOneClient.local().close(demo=True)["headline"]
  ```
- MCP: `{"tool":"seller_close","args":{"demo":true}}`.

---

## 5. Tabla de umbrales (ajusta por tienda, código: `src/omni_one/packs/seller_scenarios.py`)

| Clave | Valor | Dispara cuando | Acción |
|---|---|---|---|
| rotura de stock | 5d | velocidad 7d vs existencias < 5 días | `reorderProduct` |
| cobertura | 14d | `reorder_qty = ceil(velocity×14 − on_hand)` | pedir 14 días de cobertura |
| comisiones altas | 12% | comisiones / GMV × 100 ≥ 12% | `reviewPricing` |
| pérdida de envío | 20% | envío / GMV × 100 ≥ 20% por pedido | `adjustShipping` |
| suelo de margen | 10% | margen neto < 10% | `reviewPricing` |
| cola de DMs | 3 | ≥ 3 DMs abiertos | `triageDMs` |
| descuadre de precio | 5% | mismo SKU ±5% entre canales | `alignPrice` |

Urgencia que usa el paquete del cierre:

| `days_left` | Etiqueta | Haz |
|---|---|---|
| < 3d | `ORDER TODAY` | envía la PO hoy |
| 3–5d | `this week` | anota en agenda + confirma ETA |
| > 5d | sano | revisa mañana |

Fórmulas (deterministas, sin LLM para números):

| Métrica | Fórmula | Demo dorada |
|---|---|---|
| beneficio real | GMV − comisiones − envío − COGS | GMV $274.00 → beneficio $169.09 (61.7%) |
| ticket medio (AOV) | GMV / pedidos | ≈ $34.25 en demo |
| dinero en riesgo | reclamaciones sin responder × AOV | 3 × $34.25 ≈ $102.75 |
| velocidad diaria | vendidos_7d / 7 | Tote: 6 / 7 ≈ 0,857/d |
| días restantes | existencias / velocidad | Tote: 2 / 0,857 ≈ 2,3d → ORDER TODAY |
| cantidad a pedir | ceil(velocidad × 14 − existencias) | Tote: ceil(12 − 2) = x10 |
| % comisiones | comisiones / GMV × 100 | ≥ 12% → fuga |
| % envío | envío / GMV × 100 por pedido | ≥ 20% → fuga |
| margen neto | (GMV − comisiones − envío) / GMV × 100 (rápido) | < 10% → PROFIT_DIP |

Stock muerto: existencias ≥ 5 con cero ventas 7d → `markDownProduct` (lote/liquidación).
Pico de COGS: $ proveedor / GMV > 1,5× → `renegotiateSupplier`.
Hueco de ficha: ventas ≥ 2 con cero reseñas → `requestReview` (pedir UGC).

---

## 6. Los 12 escenarios (demos de 60 segundos)

Ejecuta: `POST /api/v1/seller/scenarios/run {"demo":true}`.
Verifica: `PYTHONPATH=src python -m pytest tests/unit/test_seller_scenarios.py -q`.

| # | Escenario | Severidad | Disparador | Evidencia | Acción de taller |
|---|---|---|---|---|---|
| 1 | STOCKOUT_RISK | `high` | existencias < 5d. Demo: Tote 2 uds, 6/7d = 2,3d | `[inventory.csv:2] Tote 2 left` | `reorderProduct` |
| 2 | DEAD_STOCK | `medium` | existencias ≥ 5, cero ventas 7d → liquidación | `[inventory.csv]` | `markDownProduct` |
| 3 | UNANSWERED_COMPLAINT | `critical` | DM negativo sin respuesta siguiente | `[instagram_dm.txt:1] Alice…` | `messageCustomer` |
| 4 | REFUND_RISK | `critical` | lenguaje de reembolso/devolución/no-llegado | `[dm:1] …` | `messageCustomer` SLA 2h |
| 5 | REVIEW_CRISIS | `high` | 1–2 estrellas o roto/dañado | `[reviews.csv:3] …` | `replyReview` |
| 6 | DM_BACKLOG | `medium` | ≥ 3 DMs abiertos | `[dm:1]` más antiguo | `triageDMs` |
| 7 | FEE_CREEP | `medium` | comisiones/GMV ≥ 12% | `[orders] fees $…` | `reviewPricing` |
| 8 | SHIPPING_LOSS | `medium` | envío/GMV ≥ 20% en el pedido | `[shopify:5] ship $…` | `adjustShipping` |
| 9 | PROFIT_DIP | `high` | margen neto < 10% | `[orders] net $…` | `reviewPricing` |
| 10 | SUPPLIER_COGS_SPIKE | `medium` | $ proveedor / GMV > 1,5× | `[supplier_invoice…]` | `renegotiateSupplier` |
| 11 | PRICE_MISMATCH | `low` | mismo SKU ±5% entre Shopify/Etsy | `[orders] {shopify:28, etsy:30}` | `alignPrice` |
| 12 | LISTING_GAP | `low` | ventas ≥ 2, cero reseñas → pedir UGC | `[orders] sold N` | `requestReview` |

Orden de severidad: `critical` → `high` → `medium` → `low`.
IDs estables (hash `_sid` de tipo+clave) → idempotente: mismos eventos → mismas decisiones.
`scenarios_to_workshop()` ancla a `Product:*` (sin fantasmas) con upsert por `stable_id`.
Técnica: `packs/seller_scenarios.py:1` agregación `_ctx()` O(n) en una pasada, funciones puras.

---

## 7. Formato de cita (la única regla)

> **Sin cita, no hay acción.** El cierre se niega a inventar tareas.
> Si te dice que repongas, muestra `[inventory.csv:2]`.
> Si te dice que respondas, muestra `[instagram_dm.txt:4]`.

| Patrón | Ejemplo | Significado |
|---|---|---|
| `[inventory.csv:2]` | `Reorder Tote — 2.3d left [inventory.csv:2]` | fila 2 del archivo de inventario |
| `[instagram_dm.txt:4]` | `Unanswered complaint [instagram_dm.txt:4]` | línea 4 de la exportación de DMs |
| `[reviews.csv:3]` | `Bad review [reviews.csv:3]` | fila 3 de las reseñas |
| `[shopify_orders.csv:5]` | `Shipping loss [shopify_orders.csv:5]` | fila 5 de los pedidos |
| `[supplier_invoice.jpg:1]` | `COGS $… [supplier_invoice.jpg:1]` | línea 1 del OCR + lateral `.jpg.txt` |

Reglas:

- Cada número del titular tiene cadena de citas en `close.json`.
- Si un número no tiene cita, no te fíes — corrige el archivo fuente, no la hoja.
- El emparejado es difuso (`Tote` ≈ `Tote Bag Handmade`) pero los nombres exactos son a prueba de balas — renombra para que coincidan.
- La deduplicación es por hash de contenido: contenido idéntico (`.jpg` + `.jpg.txt` + `.txt`) cuenta una vez. Revisa `files_ingested` vs `files_seen` en el briefing.
- Las cadenas `file:line` nunca se traducen — mantén verbatim en docs ES/ZH.

---

## 8. Archivos de entrada (suelta tu desorden, tal cual)

Los analizadores autodetectan, sin renombrar. Nombra los pedidos `shopify_*`, `etsy_*`, `amazon_*` para mejor detección de canal.

| Archivo | Qué es | Notas |
|---|---|---|
| `shopify_orders.csv` / `etsy_settlement.csv` / `amazon_*.csv` | pedidos (cualquier cabecera) | El Sniffer maneja delimitador `;` + BOM (`UTF-8-SIG`) |
| `inventory.csv` | existencias + columna `supplier` | los nombres deben coincidir con los pedidos |
| `reviews.csv` | reseñas con estrellas | 1–2★ o palabras de daño disparan crisis |
| `instagram_dm.txt` / `tiktok_dm.json` | DMs como texto/JSON | las capturas no se analizan — pega el texto |
| `supplier_invoice.jpg/png/pdf/txt` | COGS por OCR o CSV | OCR Tesseract + lateral `.jpg.txt` con dedup por hash |
| `examples/my_shop_template/*.csv` | plantillas vacías | copia a la carpeta, rellena huecos |

Receta de carpeta día 1:

```bash
mkdir -p ~/my_shop
# suelta: exportaciones de pedidos + inventory.csv + reseñas + DMs + facturas
omni-one briefing --folder ~/my_shop   # confirma GMV dentro del 5% del panel
omni-one close --folder ~/my_shop --out ./close_day1
```

---

## 9. Archivos de salida (artefactos que ya usas)

| Archivo | Para quién | Contiene |
|---|---|---|
| `close.json` | API / MCP / automatización | todo: titular, kpis+money_at_risk, do_today, reorder_sheet, reply_queue+drafts, leaks, listing_fixes, po_draft |
| `close.csv` | contador / hojas | KPIs + acciones + fugas (Sección A: fees/shipping/cogs; `money_leaks`) |
| `reorder.csv` | proveedor | producto, existencias, días restantes, cant. 14d, proveedor, cita |
| `replies.txt` | tú (copia-pega) | borradores + email de PO en un archivo imprimible |
| `po.txt` | proveedor | envía tal cual: `Subject: Reorder — Acme Textiles: Tote x10 (2 left, 2.3d supply) [inventory.csv:2]` |
| `briefing.csv` | hojas | exportación vía `omni-one export` / `GET /api/v1/seller/export.csv` |

Mapa de mañana (de `docs/DAILY_CLOSE.md`):

| Min | Tú haces | El cierre te da |
|---|---|---|
| 0–1 | Lee el titular | `Profit $169.09 (61.7%) · $102.75 at risk in 3 angry messages · 1 reorder TODAY · 0 leaks` |
| 1–3 | Copia-pega respuestas | `replies.txt`: 3 borradores con nombre, motivo, cita del pedido |
| 3–4 | Envía la PO | `po.txt`: reposición con cita |
| 4–5 | Archiva + corrige | `close.csv` → contador; corrige 1 ficha de `listing_fixes` |

Bucle de hábito:

- Día 1: soltar carpeta → paquete del cierre → 1 reembolso salvado ≈ paga el año (es $0).
- Día 7: catálogo de proveedor + velocidad aprendidos → cantidad más lista, PO en un clic.
- Día 30: racha `money_at_risk → $0` + tendencia de margen → el cierre se vuelve tu PyG.

---

## 10. Tabla de severidad de incidentes + runbooks (la primera hora gana)

### Escala de severidad (todos los runbooks)

| Sev | Significado | Tiempo de respuesta | Quién |
|---|---|---|---|
| S1 crítico | Perdiendo dinero *ahora mismo* (contracargo, rotura del nº1, aviso de cuenta) | < 1h | tú, deja todo |
| S2 alto | Costará dinero en días (2d de stock, 1 estrella con visitas, salto de comisiones) | < 4h | tú, hoy |
| S3 medio | Erosión de margen / sangría lenta | esta semana | bloque agendado |
| S4 bajo | Vigilar, sin acción | nota + re-revisa | próximo cierre |

Orden cuando todo arde: rotura (se paran ingresos) → 1 estrella (reputación) → comisiones (margen). Dilo en voz alta.

### Runbook A — ROTURA DE STOCK

Detecta: `reorder.csv` muestra el nº1 `ORDER TODAY` (`days_left` < 3),
o alerta `Stockout risk: X only N left, D days supply` + `[inventory.csv:N]`.

| Señal | Sev |
|---|---|
| `days_left` < 1 en top-3 | S1 |
| `days_left` 1–3 en cualquier SKU | S2 |
| `days_left` 3–5 | S3 |
| Sin archivo de inventario / producto sin emparejar | S2 (ciego = peligroso) |

Actúa (S1/S2, caja de 30 min): confirma `on_hand` en estantería → envía `po.txt` (pide tracking + envío parcial)
→ protege la ficha (sube precio 10–15% / limita cantidad / pausa ads; mejor que sobrevender)
→ avisa a compradores en espera (plantilla 19) → pedido de prueba al proveedor backup si ETA > `days_left`.

### Runbook B — RESEÑA DE 1 ESTRELLA

Detecta: `at_risk` salta, `reply_queue` gana fila `review`, o `REVIEW_CRISIS` + `[reviews.csv:N]`.

| Señal | Sev |
|---|---|
| 1★ en best seller + seguridad/alergia/contracargo | S1 |
| 1–2★ con daño/retraso concreto, < 24h | S2 |
| 1–2★ vaga, antigua | S3 |
| 3★ constructiva | S4 |

Actúa (S1/S2, caja de 45 min): lee `[reviews.csv:line]` → respuesta pública una vez (plantilla 08, nunca discutir ni hablar de reembolso en público)
→ DM privado con opción (plantilla 05/06, S1 empieza con reembolso)
→ corrige la causa para el próximo comprador hoy → registra: fecha, SKU, reclamo, coste, fix.

### Runbook C — PICO DE COMISIONES / COLAPSO DE MARGEN

Detecta: `money_leaks` muestra `fee_creep` (comisiones ≥ 12% GMV), o margen cae > 5 pts WoW, o el canal anuncia subida.

| Señal | Sev |
|---|---|
| Margen combinado < 0% | S1 — para tráfico pagado + pausa el peor SKU hoy |
| Margen 0–10% durante 2+ semanas | S2 |
| Subida de un canal anunciada | S3 |
| Deriva de envío (+$1/pedido) | S3 |

Actúa (S1/S2, caja de 60 min): verifica en `close.csv` Sección A (comisiones vs envío vs cogs — distintos dueños)
→ comisiones: repricing (`fee_delta / (1 − fee_rate)`; 2 pts en $28 ≈ +$1) o re-encamina los próximos 10 pedidos
→ envío: re-pesa el paquete cerrado, ajusta la caja
→ COGS: +5% sin aviso = email en 48h; COGS > 45% del retail en top-3 = repricing + renegociar
→ mata/corrige el peor vendedor: liquidación / lote / deslista.

Reglas cruzadas: un incidente a la vez · escribe citas mientras actúas
· todo con tiempo (bueno en 2h gana a perfecto mañana)
· post-mortem 5 líneas máx · sabe cuándo no es incidente (S4, ±2 pts, martes lento).

---

## 11. Tabla de comisiones + matemática de margen

| Canal | Comisión | En ejemplo $28 | Nota |
|---|---|---|---|
| Etsy | ≈ 6.5% + $0.20 | ≈ $2.02 | el fijo castiga cestas pequeñas |
| Shopify | ≈ 2.9% + $0.30 | ≈ $1.11 | más barato para volumen propio |
| Amazon | ≈ 15% | ≈ $4.20 | solo SKUs de alto margen aquí |
| Alarma combinada | ≥ 12% del GMV | — | dispara `FEE_CREEP`, revisa precio/canal |

Reglas de pulgar:

- Subida necesaria ≈ `fee_delta / (1 − fee_rate)`.
- Si las combinadas > 12% del GMV, elige un SKU para repricing o cambio de canal.
- Suelo de margen: margen real combinado ≥ 10%. Debajo 2 semanas = incidente S2.
- COGS > 45% del retail en top-3 = repricing + renegociar en paralelo.
- Pérdida de envío por pedido ≥ 20% = `adjustShipping` (re-pesa, ajusta caja, incluye en precio).
- Di tu % de comisiones de memoria con 1 punto de margen (taladro día 4).

---

## 12. Solución de problemas (síntoma → causa → fix)

| Síntoma | Causa probable | Fix |
|---|---|---|
| Beneficio demasiado alto | falta factura → COGS infracontado | suelta la factura `.txt`/foto en la carpeta |
| Beneficio demasiado bajo | factura duplicada (`.jpg` + `.jpg.txt` + `.txt`) | el dedup es automático; revisa `files_ingested` vs `files_seen` |
| `reorder.csv` vacío pero estantería vacía | nombres distintos (`Tote` vs `Tote Bag Handmade`) | renombra igual; exacto es a prueba de balas |
| Cola vacía pero hay quejas | DMs como capturas, no texto | exporta `.txt`/`.json` o pega en `instagram_dm.txt` |
| Comisiones raras | canal mal detectado por nombre | nombra `shopify_*`, `etsy_*`, `amazon_*` |
| CSV con `;` ignorado | exportación local (`;`) | soportado — el Sniffer lo maneja; revisa UTF-8 |
| Caracteres raros (`ï»¿`) | BOM de Excel | soportado (`UTF-8-SIG`) |
| 0 filas de un archivo | codificación / sin cabeceras | abre como UTF-8, confirma fila de cabecera |

---

## 13. Números dorados (sábelos de memoria)

| Número | Valor | Dónde |
|---|---|---|
| beneficio demo | $169.09 (61.7%) sobre $274.00 GMV | titular `close --demo` |
| dinero en riesgo | $102.75 en 3 mensajes (variante $82 en doc viejo) | titular `close --demo` |
| reposición Tote | 2 uds, 6 vendidos/7d → 2,3d → ORDER TODAY x10 | `reorder.csv` demo |
| alarma comisiones | 12% | `money_leaks` |
| alarma envío | 20% | por pedido |
| suelo margen | 10% | combinado |
| SLA P0 | 2h | respuestas |
| servidor | `http://localhost:5003`, docs `/api/docs` | `serve` |
| coste | $0, offline, LLM simulado por defecto | `SELLER_LLM=mock` |
| tests | 35 en verde (v1.1) | `make test` |

Gancho de roadmap — Ahora / Siguiente / Después / Más tarde:

- **Ahora (v1.1):** ritual del Cierre diario. `close` → beneficio + reposición/PO + borradores + fugas.
- **Siguiente (v1.2):** hábito — cron 7am + email, racha `money_at_risk → $0`, tendencia de margen, comparativa multi-tienda, borradores ES/ZH, parser TikTok.
- **Después (v1.3):** más listo — catálogo de costes DuckDB, conteo por foto, webhook de reseñas, propuesta de precio en un clic.
- **Más tarde:** cierre por email alojado, portal CSV del contador, red de proveedores, one-pager móvil.
- Principios: $0 por defecto, offline primero, números citados, sin tareas fantasma, LLM simulado por defecto, datos en el portátil.

Punteros: `src/omni_one/packs/seller_close.py` · `tests/unit/test_daily_close.py` (4 tests dorados)
· `examples/daily_close_demo.py` · `docs/SCENARIOS.md` · `.github/ISSUE_TEMPLATE/seller_scenario.yml`.

| `locale` (cierre) | `en` | solo borradores: idioma de respuestas + PO; KPIs/citas idénticos |
