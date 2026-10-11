# Notebooks — Seller OS walkthroughs (WAVE2-H)

Four narrative notebooks over the demo shop (profit **169.09**) + `evals/corpus_big` (40 shops).

| nb | cells | topic |
|----|-------|-------|
| `01-daily-close-walkthrough.ipynb` | 35 | briefing KPIs, reorder math, reply drafts, leaks, exports |
| `02-true-profit-deepdive.ipynb` | 29 | fee heuristics per channel, COGS catalog, margin math, 3 worked examples |
| `03-stockout-math.ipynb` | 27 | velocity/days_left/14d-cover, Tote worked example, urgency bands, dead-stock |
| `04-multi-shop-week.ipynb` | 21 | weekly_trend concept, 3-day margin walk, multi-shop compare |

All code cells use **stdlib + repo imports only** (`pathlib`, `csv`, `json`, `collections`, `math` + `omni_one.packs.seller_*`).
All outputs are **captured inline** — reads without executing.

## Env

```bash
pip install -r requirements-seller.txt
# needs: fastapi, pandas, duckdb, pillow, matplotlib (for API/demo), but notebooks run on stdlib+repo alone
```

## Run

```bash
# read without executing (outputs pre-filled):
# open *.ipynb in Jupyter / VSCode

# re-execute all (requires demo folder):
PYTHONPATH=src python3 scripts/demo_seller_os.py --folder /tmp/seller_demo_check
jupyter nbconvert --to notebook --execute notebooks/01-daily-close-walkthrough.ipynb --output /tmp/01-out.ipynb --ExecutePreprocessor.timeout=120
jupyter nbconvert --to notebook --execute notebooks/02-true-profit-deepdive.ipynb --output /tmp/02-out.ipynb --ExecutePreprocessor.timeout=120
jupyter nbconvert --to notebook --execute notebooks/03-stockout-math.ipynb --output /tmp/03-out.ipynb --ExecutePreprocessor.timeout=120
jupyter nbconvert --to notebook --execute notebooks/04-multi-shop-week.ipynb --output /tmp/04-out.ipynb --ExecutePreprocessor.timeout=120
```

## Validate

```bash
python3 -c "import json,glob; [json.load(open(f)) for f in glob.glob('notebooks/*.ipynb')]; print('notebooks valid')"
```

Demo golden: GMV $274.00, fees $16.71, ship $24.00, COGS $64.20, profit **$169.09**, margin 61.7%, 8 orders, Tote 6u/2 left/2.3d/reorder 10.
