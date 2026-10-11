# Hoja de ruta

> Ritual primero, hábito después, inteligencia después. Sin cambiar los principios.
> $0 por defecto, offline primero, números citados, sin tareas fantasma.

## Ahora (v1.1): ritual del Cierre diario

**Now (v1.1): Daily Close ritual.** `omni-one close` → profit + reorder/PO + reply drafts + leaks.
Golden: profit $169.09, Tote ORDER TODAY, $82 at risk. 35 tests green.

En español:

- Un comando (`omni-one close --demo --out ./close_today`) genera el paquete completo.
- Beneficio real (no GMV): GMV − comisiones − envío − COGS.
- Reposición con cita: Tote 2 uds → 2,3d → `ORDER TODAY x10` (`[inventory.csv:2]`).
- Respuestas con borradores deterministas (sin alucinación, $0).
- Fugas con $: comisiones ≥ 12%, envío ≥ 20%, margen < 10%.
- Dorado: beneficio $169.09, Tote `ORDER TODAY`, $82 en riesgo (variante $102.75 con 3 mensajes).
- 35 tests en verde. Verifica con `make test`.

## Siguiente (v1.2): hábito

**Next (v1.2): habit.** 7am cron + email, `money_at_risk → $0` streak, margin trend across closes,
multi-shop compare, Spanish/Chinese DM drafts, TikTok Shop parser improvements.

En español:

- Cron 7am + email: el cierre te espera en la bandeja, no al revés.
  ```cron
  0 7 * * * cd /path/to/omni-one && PYTHONPATH=src python3 -m omni_one.cli close --folder ./data/inbox --out ./close_$(date +\%F) >> ./close_cron.log 2>&1
  ```
- Racha `money_at_risk → $0`: días seguidos sin dinero en riesgo.
- Tendencia de margen entre cierres (¿sube o se erosiona?).
- Comparativa multi-tienda (¿qué tienda aguanta el margen?).
- Borradores de DM en español/chino (plantillas localizadas, citas intactas).
- Mejoras del parser de TikTok Shop (más canales, mismos `file:line`).

## Después (v1.3): más listo

**Then (v1.3): smarter.** Cost catalog persistence (DuckDB supplier memory across days),
shelf-photo stock count, review auto-triage webhook, one-click price-align proposals.

En español:

- Persistencia del catálogo de costes (memoria de proveedores en DuckDB entre días).
- Conteo de stock por foto de estantería (`on_hand` desde foto).
- Webhook de auto-clasificación de reseñas (crisis 1–2★ directa a la cola).
- Propuestas de alineación de precio en un clic (`PRICE_MISMATCH` ±5% → alinear).

## Más tarde: escala amable

**Later:** hosted close-by-email (forward inbox → close reply), accountant portal CSV,
supplier network (po.txt → send), mobile one-pager.

En español:

- Cierre por email alojado (reenvía inbox → recibe respuesta del cierre).
- Portal CSV del contador (mes cerrado en un clic).
- Red de proveedores (`po.txt` → envío directo).
- One-pager móvil (el titular + 3 botones).

## Principios que no cambian

Principles that don't change: $0 default, offline-first, cited numbers, no phantom tasks,
mock-by-default LLM, private data (laptop-first). Propose a scenario via
`.github/ISSUE_TEMPLATE/seller_scenario.yml`.

En español:

- $0 por defecto (mock primero, pago solo si tú lo pides).
- Offline primero (el portátil es el centro, la nube es opcional).
- Números citados (`file:line` o no existe).
- Sin tareas fantasma (anclado a `Product:*` con `stable_id`).
- LLM simulado por defecto (`SELLER_LLM=mock`).
- Datos privados (portátil primero).
- Propón un escenario vía `.github/ISSUE_TEMPLATE/seller_scenario.yml`.

## Cómo leer este roadmap

- [ ] Si estás en v1.1: domina el ritual de 5 min (`docs/es/CIERRE_DIARIO.md`).
- [ ] Si pides v1.2: vota por cron+email o borradores ES (abre issue con la plantilla).
- [ ] Si pides v1.3: aporta fotos de facturas/estantería para entrenar OCR/conteo.
- [ ] Métrica norte: `money_at_risk → $0` + margen ≥ 10% dos semanas seguidas.
