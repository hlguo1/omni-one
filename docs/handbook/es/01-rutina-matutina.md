# Rutina matutina — el cierre diario de 5 minutos (plan de adopción de 7 días)

> **Objetivo:** cada mañana, antes de empaquetar un solo paquete, saber
> (1) si realmente gané dinero ayer, (2) qué se va a agotar,
> (3) quién está enfadado ahora mismo. Un comando, sin conexión, $0:
>
> ```bash
> omni-one close --folder ~/my_shop --out ./close_today
> ```
>
> Obtienes `close.json` + `close.csv` + `reorder.csv` + `replies.txt` + `po.txt`.
> Imprímelos, o simplemente lee el **titular** — una línea escrita para cerebro con café.

## El titular, descifrado

```
Profit $169.09 (61.7%) · $102.75 at risk in 3 angry messages · 1 reorder(s) TODAY · 0 leak(s) to plug
```

| Fragmento | Significado | De dónde viene |
|---|---|---|
| `Profit $169.09 (61.7%)` | Beneficio real = GMV − comisiones − envío − COGS, más margen | CSVs de pedidos + facturas de proveedores |
| `$102.75 at risk in 3 angry messages` | Exposición a reembolsos ≈ 3 × AOV en reclamaciones sin responder | DMs + reseñas de 1–2★ |
| `1 reorder(s) TODAY` | SKUs con < 3 días de stock restante | velocidad vs existencias |
| `0 leak(s) to plug` | Anomalías de comisiones/envío/margen | cálculo de comisiones del canal |

Cada número cita `[file:line]`. Si un número no tiene cita, no te fíes —
corrige el archivo fuente, no la hoja de cálculo.

## El ritual de 5 minutos (cada día)

- [ ] **0:00–0:30 — Ejecuta el cierre.** `omni-one close --folder … --out …`. Lee el titular en voz alta.
- [ ] **0:30–2:00 — Respuestas primero.** Abre `replies.txt`. Copia-pega el borrador #1, personaliza una frase, envía. Repite mientras hierve el agua. Regla: **P0 (reembolso / no-ha-llegado / dañado) en menos de 2 horas, sin excepciones.** Ver `03-respuestas.md`.
- [ ] **2:00–3:30 — Reposiciones.** Abre `reorder.csv`. Todo lo que sea `ORDER TODAY` → envía el borrador de `po.txt` a ese proveedor *hoy*. Lo que sea `this week` → anótalo en la agenda. Ver `02-proveedores.md`.
- [ ] **3:30–4:30 — Una fuga.** Si `money_leaks` no está vacío, haz la corrección más barata (normalmente: subir un precio $1, o mover un SKU fuera del canal caro). Regístralo.
- [ ] **4:30–5:00 — Archiva.** Mueve las exportaciones del día a la carpeta de la tienda, añade una línea a tu libro (ver `04-contador.md`).

## Plan de adopción de 7 días

### Día 1 — Suelta la carpeta (15 min, una sola vez)
- [ ] Crea `~/my_shop/` y mete: exportaciones de pedidos de Shopify/Etsy/Amazon, `inventory.csv`, exportación de reseñas, exportación de DMs (`.txt` o `.json`), facturas de proveedores (fotos o `.txt`).
- [ ] Ejecuta `omni-one briefing --folder ~/my_shop`. Confirma que el GMV parece más o menos correcto (dentro del 5% de lo que dice el panel del canal).
- [ ] Ejecuta `omni-one close --folder ~/my_shop --out ./close_day1`. Lee cada archivo una vez. Aún no actúes — solo calibra la confianza.
- [ ] **Listo cuando:** el titular de beneficio no te sorprenda más del 20%.

### Día 2 — Solo respuestas
- [ ] Ejecuta el cierre. Trabaja *solo* la cola de respuestas. Envía cada borrador P0 (editado, no a ciegas).
- [ ] Cuenta respuestas enviadas vs longitud de la cola. Objetivo: bandeja cero en P0s.
- [ ] **Listo cuando:** la cola de respuestas está vacía o cada pendiente tiene fecha en la agenda.

### Día 3 — Proveedores
- [ ] Ejecuta el cierre. Lee `02-proveedores.md` secciones 1–2.
- [ ] Envía la primera PO real desde `po.txt` (o confirma que el stock está sano — también es un resultado).
- [ ] Anota los costes unitarios de tus 3 SKUs principales en un cuaderno. Esta es tu biblia de COGS ahora.
- [ ] **Listo cuando:** una PO enviada, o confirmación escrita de que no hay que reponer.

### Día 4 — Comisiones y fugas
- [ ] Ejecuta el cierre. Abre `close.csv`, sección `money_leaks`.
- [ ] Calcula tu % de comisiones por canal (Etsy ≈ 6.5%+$0.20 · Shopify ≈ 2.9%+$0.30 · Amazon ≈ 15%). Si las comisiones combinadas > 12% del GMV, elige un SKU para repricing o cambio de canal.
- [ ] **Listo cuando:** puedes decir tu % de comisiones de memoria con 1 punto de margen.

### Día 5 — Ciclo completo, cronometrado
- [ ] Haz todo el ritual con cronómetro. Objetivo: menos de 5 minutos sin contar el envío de mensajes.
- [ ] Ejecuta `omni-one scenarios --folder ~/my_shop` una vez y lee las 3 decisiones principales. Ese es el trabajo de mañana, no de hoy.
- [ ] **Listo cuando:** cierre → respuestas → reposición → fuga → archivo, todo en 30 minutos de reloj.

### Día 6 — Paquete del contador
- [ ] Sigue `04-contador.md` pasos de conciliación 1–4 con los cierres de esta semana.
- [ ] Envía a tu contador (o a tu yo futuro) `close.csv` + `reorder.csv` de la semana.
- [ ] **Listo cuando:** una semana de cierres concilia con el extracto bancario dentro de $5.

### Día 7 — Simulacro de incidente
- [ ] Elige un runbook de `05-incidentes.md` (rotura de stock, 1 estrella, pico de comisiones) y recórrelo en seco — encuentra las citas, redacta los mensajes, calcula la corrección.
- [ ] Anota tus umbrales personales (¿cuántos días de cobertura? ¿qué suelo de margen?).
- [ ] **Listo cuando:** puedes ejecutar cualquiera de los tres runbooks sin releer la teoría.

## Listas de control

### Diaria (plastifica esto)
- [ ] Cierre ejecutado, titular leído
- [ ] Todas las respuestas P0 enviadas < 2h
- [ ] POs ORDER TODAY enviadas
- [ ] Una fuga tocada
- [ ] Archivos archivados

### Semanal (viernes, 20 min)
- [ ] 7 cierres conciliados, GMV vs paneles ±2%
- [ ] ETAs de proveedores reclamados (todo pedido hace > 7 días sin tracking)
- [ ] Stock muerto listado (0 ventas + 5+ unidades → borrador de liquidación)
- [ ] Precios revisados frente a cambios de comisiones
- [ ] Copia de seguridad: copia `~/my_shop` a USB / segunda máquina

### Mensual (primer lunes, 1 h)
- [ ] `close.csv` del mes → paquete del contador (`04-contador.md`)
- [ ] Tarjeta de puntuación de proveedores actualizada (precio, ETA, tasa de defectos)
- [ ] Peor decisión de venta: matar, empaquetar o liquidar
- [ ] Control de suelo de margen: ¿margen real combinado ≥ 10%? Si no, ver playbook de fugas

## Solución de problemas

| Síntoma | Causa probable | Solución |
|---|---|---|
| Beneficio parece demasiado alto | Falta factura de proveedor → COGS infracontado | Suelta la factura `.txt`/foto en la carpeta |
| Beneficio parece demasiado bajo | Factura duplicada (`.jpg` + `.jpg.txt` + `.txt`) | El cierre deduplica contenido idéntico automáticamente; compara `files_ingested` vs `files_seen` en el briefing |
| `reorder.csv` vacío pero estantes vacíos | Nombres difieren entre pedidos e inventario (`Tote` vs `Tote Bag Handmade`) | Renombra para que coincidan; la coincidencia es difusa pero exacta es infalible |
| Cola de respuestas vacía pero clientes se quejan | DMs exportados como capturas, no texto | Exporta DMs como `.txt`/`.json`, o pega el texto en `instagram_dm.txt` |
| Comisiones parecen mal | Canal mal detectado por nombre de archivo | Nombra los pedidos `shopify_*`, `etsy_*`, `amazon_*` |
| CSV con punto y coma ignorado | Exportación local (`;` delimitador) | Soportado — el Sniffer lo maneja; si un archivo muestra 0 filas, comprueba que abre como UTF-8 |
| Caracteres raros (`ï»¿`) | Cabeceras BOM de Excel | Soportado (UTF-8-SIG); amplía con casos borde de `evals/generate.py --help` si pruebas |

## La única regla

> **Sin cita, sin acción.** El cierre se niega a inventar tareas. Si te dice
> que repongas, te muestra `[inventory.csv:2]`. Si te dice que respondas,
> te muestra `[instagram_dm.txt:4]`. Exígele ese estándar — y exígeselo
> también a tus proveedores, canales y contador.
