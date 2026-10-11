# 08 — Guía de temporada alta (fiestas, promos, viralidad)

1. Dos semanas antes: sube `COVER_DAYS` 14 → 21 en superventas, confirma ETA por escrito.
2. En pico: cierre DOS veces (7am + 7pm). SLA 2h → 1h; un `UNANSWERED_COMPLAINT` de +4h
   es un reembolso — trátalo como tal.
3. Precios congelados: sin ediciones salvo `PRICE_MISMATCH` — alinea hacia ARRIBA, nunca
   a la baja. Anota el motivo en `close.json`.
4. El `DEAD_STOCK` se vuelve pack: acompaña al superventas con 15% en vez de rebajar al ganador.
5. Caja: el GMV del pico miente (reembolsos tardan 7–14d). Mira `money_at_risk_usd`, no GMV.
   Reserva 20% de `true_profit` hasta que se asienten las devoluciones.
6. Después: un cierre retro (`--out ./close_peak_retro`) — peor fuga, respuesta más lenta,
   peor rotura. Ajusta exactamente un control antes del próximo pico.
