#!/usr/bin/env python3
"""Daily Close demo: writes a real close bundle to /tmp/close_demo (or ./close_today)."""
import sys
from pathlib import Path
SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
from omni_one.client import OmniOneClient
from omni_one.packs.seller_close import write_close_bundle

import sys as _sys
_loc = _sys.argv[2] if len(_sys.argv) > 2 else "en"
c = OmniOneClient.local().close(demo=True, shop="Maya's Handmade", locale=_loc)
print("HEADLINE:", c["headline"])
for t in c["do_today"]:
    print(" •", t)
paths = write_close_bundle(c, sys.argv[1] if len(sys.argv) > 1 else "/tmp/close_demo")
print("wrote:", paths)
print("open replies.txt, copy a draft, send the PO — that's the whole ritual.")
