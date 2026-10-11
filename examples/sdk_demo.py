#!/usr/bin/env python3
"""SDK demo against live API (make serve) with local fallback."""
import sys
from pathlib import Path
SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
from omni_one.client import OmniOneClient

for base in ("http://localhost:5003", ""):
    try:
        c = OmniOneClient(base) if base else OmniOneClient.local()
        print(f"== {base or 'local'} ==")
        print("health:", c.health())
        print("kpis:", c.briefing_demo()["kpis"])
        print("scenarios total:", c.scenarios_run()["total"])
        break
    except Exception as e:
        print(f"{base or 'local'} failed: {e}")
