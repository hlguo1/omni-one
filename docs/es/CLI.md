# CLI

> Un binario, nueve comandos, cero fricción. Todo offline y $0 por defecto.
> Alternativa sin instalar: `PYTHONPATH=src python3 -m omni_one.cli ...`.

## Forma de uso

`omni-one` (after `pip install -e .`) or `PYTHONPATH=src python3 -m omni_one.cli ...`.

Instalación mínima:

```bash
pip install -r requirements-seller.txt && pip install -e .
omni-one doctor
```

## Tabla de comandos

| Command | What |
|---|---|
| `omni-one doctor` | env + deps + pipeline smoke |
| `omni-one demo` | Seller demo briefing |
| `omni-one briefing --demo --json b.json` | briefing; `--folder /p` for real shop |
| `omni-one scenarios --demo` | 12 scenarios ranked |
| `omni-one operations` | full ontology→workshop→AIP→audit loop |
| `omni-one close --demo --out ./close_today` | **Daily Close bundle** (json/csv/reorder/replies/po) |
| `omni-one export --demo --out briefing.csv` | briefing CSV |
| `omni-one serve --port 5003` | API server |
| `omni-one evaluate --n 500` | eval harness |

`make demo|close|test|e2e|serve|docker|lint|doctor` wraps the same.

## Guía comando por comando (ES)

- `omni-one doctor`: verifica entorno, dependencias y humo del pipeline. Ejecútalo tras instalar y antes de reportar un fallo.
- `omni-one demo`: muestra el briefing demo del vendedor con datos dorados (`Profit $169.09`).
- `omni-one briefing --demo --json b.json`: genera el briefing; con `--folder /p` apunta a tu tienda real (`~/my_shop`, `/tmp/my_shop`).
- `omni-one scenarios --demo`: ordena los 12 escenarios (rotura, reembolso, comisiones, etc.) por severidad.
- `omni-one operations`: corre el bucle completo ontología→taller→AIP→auditoría sin fantasmas (`Product:*` + `stable_id`).
- `omni-one close --demo --out ./close_today`: **el ritual**. Escribe `close.json` + `close.csv` + `reorder.csv` + `replies.txt` + `po.txt`.
- `omni-one export --demo --out briefing.csv`: exporta el briefing a CSV para hojas/contador.
- `omni-one serve --port 5003`: levanta la API en `http://localhost:5003` (docs en `/api/docs`).
- `omni-one evaluate --n 500`: corre el arnés de evaluación con N registros (métricas en vivo).

## Recetas copiables

Ritual diario con tu tienda:

```bash
omni-one close --folder ~/my_shop --out ./close_today
cat ./close_today/replies.txt
```

Demo dorada + briefing a archivo:

```bash
omni-one close --demo --out ./close_today
omni-one briefing --demo --json b.json
omni-one scenarios --demo
```

Servidor + humo:

```bash
omni-one serve --port 5003 &
curl -sf http://localhost:5003/health
PYTHONPATH=src python3 examples/sdk_demo.py
PYTHONPATH=src python3 examples/daily_close_demo.py
```

Cron 7am (cierre automático):

```cron
0 7 * * * cd /path/to/omni-one && PYTHONPATH=src python3 -m omni_one.cli close --folder ./data/inbox --out ./close_$(date +\%F) >> ./close_cron.log 2>&1
```

## Opciones comunes

| Opción | Significado | Ejemplo |
|---|---|---|
| `--demo` | datos demo incluidos | `omni-one close --demo --out ./close_today` |
| `--folder /p` | carpeta real de la tienda | `omni-one close --folder /tmp/my_shop --out ./close_2026-10-11` |
| `--out ./dir` | directorio de salida | `omni-one export --demo --out briefing.csv` |
| `--shop "Name"` | nombre visible | `omni-one close --folder /tmp/my_shop --out ./close_2026-10-11 --shop "Maya's Handmade"` |
| `--json b.json` | salida JSON | `omni-one briefing --demo --json b.json` |
| `--port 5003` | puerto API | `omni-one serve --port 5003` |
| `--n 500` | nº de registros eval | `omni-one evaluate --n 500` |

## Verificación y ayuda

- [ ] `omni-one doctor` en verde antes del primer cierre.
- [ ] `close.json` contiene `headline` con cita `file:line`.
- [ ] `reorder.csv` cita `[inventory.csv:2]` en la demo.
- [ ] Si un comando falla, re-ejecuta con `--demo` para aislar tu carpeta vs el código.
- Ver chuleta: `docs/handbook/00-quick-reference.md` y `docs/es/QUICKSTART.md`.
