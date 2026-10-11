#!/usr/bin/env python3
"""Quickstart: Seller OS briefing in-process ($0, offline)."""
import sys
from pathlib import Path
SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from omni_one.client import OmniOneClient
from omni_one.packs.seller_export import briefing_to_csv

c = OmniOneClient.local()
b = c.briefing_demo()
k = b["kpis"]
print(f"GMV ${k['gmv']:.2f}  Fees ${k['fees']:.2f}  Net ${k['net']:.2f}")
print(f"True Profit ${k['true_profit']:.2f}  Margin {k['margin_pct']:.1f}%  Orders {k['orders']}")
print(f"Best: {k['best_seller']['product']} x{k['best_seller']['qty']}")
for a in b["alerts"]:
    print(f"[{a['severity']}] {a['message']}")
for i, act in enumerate(b["actions"], 1):
    print(f"{i}. {act}")
Path("/tmp/briefing_quickstart.csv").write_text(briefing_to_csv(b))
print("wrote /tmp/briefing_quickstart.csv")
print("next: python3 -m omni_one.cli scenarios --demo  |  make serve")
