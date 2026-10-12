.PHONY: install install-dev demo briefing test test-cov e2e serve docker lint format doctor eval clean auto closes

PY ?= python3
SRC = PYTHONPATH=src

install:
	pip install -r requirements-seller.txt
	pip install -e .

install-dev:
	pip install -r requirements-seller.txt
	pip install -e ".[dev,vision]"

demo:
	$(SRC) $(PY) scripts/demo_seller_os.py --folder /tmp/seller_demo

close:
	$(SRC) $(PY) -m omni_one.cli close --demo --out ./close_today --locale $(LOCALE)

auto:
	$(SRC) $(PY) -m omni_one.cli auto --out ./auto_today

closes:
	$(SRC) $(PY) -m omni_one.cli returns-close --out /tmp/closes/returns
	$(SRC) $(PY) -m omni_one.cli cashflow-close --out /tmp/closes/cashflow
	$(SRC) $(PY) -m omni_one.cli reputation-close --out /tmp/closes/reputation
	$(SRC) $(PY) -m omni_one.cli forecast-close --out /tmp/closes/forecast
	$(SRC) $(PY) -m omni_one.cli rollup-close --out /tmp/closes/rollup

briefing:
	$(SRC) $(PY) -m omni_one.cli briefing --demo

scenarios:
	$(SRC) $(PY) -m omni_one.cli scenarios --demo

test:
	$(SRC) $(PY) -m pytest tests/unit tests/integration -q

test-all:
	$(SRC) $(PY) -m pytest tests/unit tests/integration -q
	$(SRC) $(PY) -m pytest sdks/gen/python/tests/ -q
	node sdks/gen/typescript/tests/contract.mjs
	node sdks/ts/tests/run.mjs
	$(PY) sdks/gen/regen.py | tail -n 1

test-cov:
	$(SRC) $(PY) -m pytest tests/unit tests/integration -q --cov=src/omni_one --cov-report=term-missing

e2e:
	$(SRC) $(PY) scripts/e2e_core_methodology.py --out /tmp/e2e_method
	$(SRC) $(PY) scripts/demo_seller_os.py --folder /tmp/seller_demo | grep -E "GMV|True Profit|Stockout|Daily close"

eval:
	$(SRC) $(PY) -m omni_one.core.eval_harness --n 500

serve:
	$(SRC) $(PY) -m omni_one.cli serve --port 5003

docker:
	docker build -t omni-one:latest .
	docker compose up -d
	sleep 3
	curl -sf http://localhost:5003/health | head -c 300; echo

lint:
	ruff check src tests scripts || true
	$(PY) -m compileall -q src/omni_one

format:
	ruff check --fix src tests scripts || true

doctor:
	$(SRC) $(PY) -m omni_one.cli doctor

clean:
	find . -name "__pycache__" -type d -prune -exec rm -rf {} + 2>/dev/null || true
	rm -rf /tmp/seller_demo /tmp/e2e_method /tmp/e2e .coverage htmlcov
