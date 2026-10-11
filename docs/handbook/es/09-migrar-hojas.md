# 09 — Migrar desde hojas de cálculo (cambio de fin de semana)

Viernes: exporta todo (pedidos, inventario, pagos) como CSV a `./data/inbox`.
NO los limpies — los parsers aguantan cabeceras raras, `;`, BOM, multimoneda.

Sábado: `omni-one close --folder ./data/inbox --out ./close_first`. Compara UN número
con tu hoja: GMV. Si difiere >1%, la causa está en `ingest_report.errors` o en una fila
reembolsada que tu hoja excluía — mira `order_refund` primero.

Domingo: envía el primer `po.txt`, responde 3 borradores, entrega `close.csv` al contador
con el diccionario (`04-accountant-pack.md`). Desde el lunes: el cierre de 5 minutos
reemplaza la hoja. Déjala solo-lectura 30 días y archiva.

Lo que NO migra: lore de pivots, intuiciones con colores, GMV "ajustado". Si un número
no cita `file:line`, no cruza.
