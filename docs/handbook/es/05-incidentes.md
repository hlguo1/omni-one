# Incidentes — runbooks de rotura / 1-estrella / pico de comisiones

> Los incidentes se ganan en la primera hora. Cada runbook sigue la misma
> forma: **detecta** (qué muestra el cierre) → **triaje** (tabla de severidad) →
> **actúa** (pasos numerados con tiempos) → **seguimiento** (para que no
> recurra). Imprime esta página. Cuando salta la alerta, inicia el cronómetro.

## Escala de severidad (todos los runbooks)

| Sev | Significado | Tiempo de respuesta | Quién |
|---|---|---|---|
| S1 crítico | Perdiendo dinero *ahora mismo* (chargeback, rotura del #1, aviso de cuenta) | < 1h | tú, suelta todo |
| S2 alto | Costará dinero en días (2d de stock, 1-estrella ganando vistas, salto de comisiones) | < 4h | tú, hoy |
| S3 medio | Erosión de margen / sangría lenta | esta semana | bloque agendado |
| S4 bajo | Vigilar, sin acción | nota + rechequeo | próximo cierre |

---

## Runbook A — ROTURA (best seller a punto de llegar a cero)

**Detecta:** `reorder.csv` muestra tu #1 `ORDER TODAY` (`days_left` < 3),
o la alerta del briefing dice `Stockout risk: X only N left, D days supply`
con cita `[inventory.csv:N]`.

### Severidad

| Señal | Sev |
|---|---|
| `days_left` < 1 en top-3 | S1 |
| `days_left` 1–3 en cualquier vendedor | S2 |
| `days_left` 3–5 | S3 |
| Sin archivo de inventario / producto sin match | S2 (ciego = peligroso) |

### Actúa (S1/S2, caja de 30 min)
1. **[0–5] Confirma los números.** Abre `[inventory.csv:line]` de la cita. Mira el estante físicamente — ¿`on_hand` es real? (Típico: vendiste 3 en un mercado y olvidaste descontar.) Corrige el CSV si está mal, re-ejecuta cierre.
2. **[5–10] Envía la PO.** Copia `po.txt`, rellena huecos, envía. Pide **tracking + envío parcial** si hay stock parcial ("envía lo que tengas hoy, resto ASAP").
3. **[10–15] Protege el anuncio.** Si `days_left` < plazo: sube precio 10–15% para frenar velocidad *o* pon topes de cantidad *o* pausa ads. Un anuncio pausado vence a uno sobrevendido (las cancelaciones hunden ranking + disparan reembolsos).
4. **[15–20] Avisa a compradores en espera.** Quien pregunte por DM "dónde está mi pedido" de este SKU recibe plantilla 19 (ETA hecho-a-pedido) *antes* de enfadarse.
5. **[20–30] Alinea el respaldo.** Manual de proveedores §5: pedido de prueba al proveedor respaldo hoy si ETA principal > `days_left`.

### Seguimiento (48h)
- [ ] ¿PO confirmada con ETA por escrito? Si no, escala (llama).
- [ ] ¿Protección del anuncio aún puesta? Quítala el día que llega stock (topes rancios pierden ventas).
- [ ] Causa raíz: ¿plazo se alargó, velocidad picó, o conteo derivó? Corrige la *causa*: día de PO fijo (p. ej. cada lunes), umbral de cobertura menor para SKUs picudos, o hábito de conteo con $20 barcode.

---

## Runbook B — RESEÑA 1-ESTRELLA / CRISIS DE RESEÑAS

**Detecta:** `at_risk` del briefing salta, el cierre gana fila `review` en `reply_queue`, o escenarios listan `REVIEW_CRISIS` con evidencia `[reviews.csv:N]`.

### Severidad

| Señal | Sev |
|---|---|
| 1★ en best seller + menciona seguridad/alergia/chargeback | S1 |
| 1–2★ con detalles de daño/retraso, < 24h | S2 |
| 1–2★ vago ("no me gustó"), viejo | S3 |
| 3★ constructivo | S4 (agradece + corrige en silencio) |

### Actúa (S1/S2, caja de 45 min)
1. **[0–5] Lee, no reacciones.** Abre el exacto `[reviews.csv:line]`. Anota la afirmación *verificable* (¿roto? ¿tarde? ¿equivocado?). Comprueba la cita del pedido si es identificable.
2. **[5–15] Respuesta pública (plantilla 08).** Gracias + disculpa + indica la corrección + invita al DM. Nunca: discutir hechos, mencionar reembolsos en público (invita extorsión), ni responder dos veces. Una respuesta, luego deja de mirar el hilo.
3. **[15–25] DM privado (plantilla 05/06).** Ofrece la *elección* (reemplazo O reembolso) en una hora. Incluye la cita. Para S1, lidera con el reembolso — la velocidad vence al margen aquí.
4. **[25–35] Corrige la causa para el *próximo* comprador.** Dañado → añade paso de empaque hoy (fotografía el nuevo pack). Tarde → revisa el lote del transportista. Equivocado → re-etiqueta los bins del estante ahora, no "luego".
5. **[35–45] Regístralo.** Una línea: fecha, SKU, reclamo, verdadero/falso, coste (reembolso $X / reenvío $Y), corrección. Tres líneas idénticas en un trimestre = cambio de producto/proceso, no mala suerte.

### Seguimiento (7 días)
- [ ] ¿El comprador actualizó su reseña? (Pide amable *una vez*, plantilla 15. Nunca pagues por cambios de reseña — baneable.)
- [ ] ¿La corrección aguantó? Cero quejas repetidas en ese SKU por 2 semanas = cerrado.
- [ ] Si el reclamo fue falso/abusivo: reporta con tu rastro de evidencia (`replies.txt` + cita de pedido). Pasa página — una mala reseña entre veinte 5-estrellas convierte *mejor* (efecto autenticidad). No nukees el anuncio por eso.

---

## Runbook C — PICO DE COMISIONES / COLAPSO DE MARGEN

**Detecta:** `money_leaks` del cierre muestra `fee_creep` (comisiones ≥ 12% del GMV), o
el margen del titular cae > 5 puntos semana a semana con GMV similar, o un
canal anuncia cambio de comisiones.

### Severidad

| Señal | Sev |
|---|---|
| Margen combinado < 0% (perdiendo por pedido) | S1 — para tráfico pago + pausa peor SKU hoy |
| Margen combinado 0–10% por 2+ semanas | S2 |
| Subida de comisiones de un canal anunciada | S3 (modela esta semana) |
| Deriva de coste de envío (+$1/pedido tendencia) | S3 |

### Actúa (S1/S2, caja de 60 min)
1. **[0–10] Verifica la matemática.** `close.csv` Sección A: ¿el pico está en `fees`, `shipping`, o `cogs`? Cada uno tiene dueño distinto (canal, transportista, proveedor). No renegocies con la parte equivocada.
2. **[10–20] Comisiones → repricing o re-canal.** Regla: subida necesaria ≈ `fee_delta / (1 − fee_rate)`. Subida de 2 puntos en $28 ≈ +$0.60 — redondea a +$1 y guarda la diferencia. O mueve volumen: Etsy 6.5%+$0.20 vs Shopify 2.9%+$0.30 vs Amazon 15% — rutea los *próximos* 10 pedidos, no todo el historial.
3. **[20–30] Envío → re-pesa.** Pesa tu paquete empaquetado (no el producto). El 80% de "picos de comisiones" son en realidad peso dimensional o deriva de zona. Solución: caja a medida, cambia a tracked-lettermail bajo el umbral, o mete el envío en precio con "envío gratis" (la conversión suele cubrirlo).
4. **[30–40] COGS → revisión de proveedor.** Manual de proveedores §3 umbrales: +5% sin aviso = email en 48h. COGS > 45% del retail en top-3 SKU = repricing + renegociación en paralelo.
5. **[40–60] Mata o corrige el peor vendedor.** `kpis.worst_seller` + `listing_fixes`: liquidación (recupera caja), bundle (sube AOV), o deslista (para el sangrado). El sentimentalismo no es estrategia.

### Seguimiento (30 días)
- [ ] ¿Margen de vuelta sobre suelo 10% por 2 semanas seguidas?
- [ ] ¿El cambio de precio aguantó (sin colapso de conversión)? Vigila unidades/día 14 días post-cambio; revierte si la velocidad cae a la mitad.
- [ ] Hábito de vigilancia de comisiones: mira `money_leaks` en cada cierre (5 segundos). El cierre vigila; tú solo mira.

---

## Reglas cruzadas

1. **Un incidente a la vez.** ¿Rotura + 1-estrella + pico de comisiones juntos? Orden: rotura (ingreso para) → 1-estrella (reputación) → comisiones (margen). Dilo en voz alta.
2. **Escribe mientras haces.** Cada acción lleva su cita pegada al lado. Tu-yo-futuro (y tu contador, y el equipo de disputas del canal) necesita el rastro.
3. **Todo con tiempo.** Una respuesta perfecta enviada mañana pierde contra una buena enviada en 2 horas. El SLA es el producto.
4. **Post-mortem, 5 líneas máx:** qué saltó, qué hiciste, qué costó, qué cambiarás, fecha de verificación. Archívalo con los cierres del mes.
5. **Sabe cuándo no es incidente.** Un solo S4, un vaivén de margen dentro de ±2 puntos, un martes lento — anótalo, cierra el portátil, ve a empaquetar. El sistema funciona; déjalo.
