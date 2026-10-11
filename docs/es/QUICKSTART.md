# Inicio rápido (60 segundos, $0)

> Objetivo: pasar de cero al ritual del cierre diario en un minuto.
> Sin tarjeta, sin red, sin LLM de pago. Todo local con `SELLER_LLM=mock`.

## Requisitos

- Python 3.10+ y `pip` instalados.
- `git` instalado.
- 2 minutos de terminal. Sin Docker obligatorio para el inicio.

## Instalación en 60 segundos

```bash
git clone https://github.com/garyguo123456789/omni-one.git && cd omni-one
pip install -r requirements-seller.txt && pip install -e .
omni-one doctor                                        # deps + pipeline smoke
omni-one close --demo --out ./close_today             # THE ritual: profit + reorders + replies
cat ./close_today/replies.txt                         # copy-paste a draft, send the PO
```

Qué acaba de pasar:

- `pip install -r requirements-seller.txt` instala solo lo necesario para vendedores (ligero).
- `pip install -e .` expone el comando `omni-one` en tu `PATH`.
- `omni-one doctor` verifica entorno + dependencias + humo del pipeline.
- `omni-one close --demo` genera el paquete dorado con `demo=True`.
- `cat ./close_today/replies.txt` muestra los borradores listos para copiar-pegar.

## Tu tienda (carpeta real)

```bash
mkdir -p /tmp/my_shop
cp ~/Downloads/*orders*.csv ~/Downloads/inventory.csv /tmp/my_shop/
cp examples/my_shop_template/*.csv /tmp/my_shop/   # fill blanks if needed
omni-one close --folder /tmp/my_shop --out ./close_2026-10-11 --shop "Maya's Handmade"
```

Notas de la carpeta:

- Suelta exportaciones tal cual: `shopify_orders.csv`, `etsy_settlement.csv`, `amazon_*.csv`.
- Añade `inventory.csv` con la columna `supplier` conservada.
- Añade `reviews.csv`, `instagram_dm.txt` o `tiktok_dm.json`.
- Añade facturas `supplier_invoice.jpg/png/pdf/txt` (OCR + lateral `.jpg.txt`).
- Nombra los pedidos `shopify_*`, `etsy_*`, `amazon_*` para detectar el canal.
- El Sniffer soporta delimitador `;` y BOM `UTF-8-SIG`.
- El emparejado es difuso (`Tote` ≈ `Tote Bag Handmade`), pero exacto es mejor.

## Servidor + SDK + bot

```bash
omni-one serve --port 5003 &                            # docs at /api/docs
PYTHONPATH=src python3 examples/sdk_demo.py
PYTHONPATH=src python3 examples/daily_close_demo.py
```

Detalles:

- Base API: `http://localhost:5003`. Documentación: `/api/docs`.
- Salud: `/health`, `/readiness`, `/status`, `/ping`. Métricas: `/metrics`.
- El SDK usa `from omni_one.client import OmniOneClient`.
- Ejemplo: `OmniOneClient.local().close(demo=True)["headline"]`.
- Ver `docs/API.md` para las 18 rutas y `docs/CLI.md` para los 9 comandos.

## Claude/Cursor MCP

```bash
python3 -m omni_one.mcp_server
```

Herramientas (stdio):

- `seller_close`, `seller_briefing`, `seller_scenarios`, `seller_operations`,
- `pipeline_analyze`, `vision_analyze`.

## Verificación (¿funcionó?)

- [ ] `omni-one doctor` termina sin errores.
- [ ] `./close_today/close.json` existe y `headline` menciona `Profit $169.09`.
- [ ] `./close_today/reorder.csv` menciona `Tote x10` con `[inventory.csv:2]`.
- [ ] `./close_today/replies.txt` tiene 3 borradores con citas `[instagram_dm.txt:N]`.
- [ ] `curl -sf http://localhost:5003/health` responde `ok` si el servidor corre.

## Solución de problemas

| Síntoma | Causa | Corrección |
|---|---|---|
| `omni-one: command not found` | falta `pip install -e .` | re-ejecuta `pip install -e .` |
| Beneficio raro | falta factura o nombre distinto | añade factura; renombra productos igual |
| CSV con `;` vacío | exportación local | soportado; verifica UTF-8 |
| Caracteres `ï»¿` | BOM de Excel | soportado (`UTF-8-SIG`) |

## Siguiente paso

- Lee `docs/DAILY_CLOSE.md` (el ritual de 5 minutos).
- Lee `docs/handbook/01-morning-routine.md` (plan de 7 días).
- Lee `docs/handbook/00-quick-reference.md` (chuleta de una página).
- Propón un escenario vía `.github/ISSUE_TEMPLATE/seller_scenario.yml`.
