#!/usr/bin/env python3
"""Shop weekly demo — multi-day trend + multi-shop compare + cron + pack.

Uses omni_one.cli_extra.weekly_trend on demo folders (no network, $0):

    PYTHONPATH=src python3 examples/shop_weekly.py
    PYTHONPATH=src python3 examples/shop_weekly.py --days 5 --out /tmp/shop_weekly_out

What it does:
  1. Builds N demo seller folders (seeds 42..42+N-1) under a temp dir
     (or --out when given) via make_seller_demo_folder.
  2. Prints weekly_trend(folders) markdown (margin/profit/at-risk by day).
  3. Prints multi_shop_compare({shop: folder}) ranked table.
  4. Prints cron_install(folder0, out_base) crontab line.
  5. Builds a close bundle for day-01, writes it, runs accountant_pack,
     prints the zip path + contents.

All deterministic; every dollar cites file:line (never stripped).
See: src/omni_one/cli_extra.py, tests/unit/test_sdk_contract.py.
"""
from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from omni_one.cli_extra import (  # noqa: E402
    accountant_pack,
    accountant_pack_contents,
    cron_install,
    cron_install_help,
    multi_shop_compare,
    weekly_trend,
)
from omni_one.packs.seller_close import write_close_bundle  # noqa: E402
from omni_one.packs.seller_os import make_seller_demo_folder  # noqa: E402

try:
    from omni_one.client import OmniOneClient  # noqa: E402
    _HAS_CLIENT = True
except Exception:  # pragma: no cover
    OmniOneClient = None  # type: ignore
    _HAS_CLIENT = False


def build_demo_folders(base: Path, days: int) -> list[Path]:
    """Build `days` demo seller folders (seeds 42.., deterministic)."""
    folders: list[Path] = []
    for i in range(days):
        seed = 42 + i
        folder = base / f"day_{i + 1:02d}_seed_{seed}"
        folders.append(make_seller_demo_folder(folder, seed=seed))
    return folders


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Shop weekly demo (offline, $0).")
    parser.add_argument("--days", type=int, default=3, help="demo days to simulate (default 3)")
    parser.add_argument("--out", default=None, help="output base dir (default: temp dir)")
    parser.add_argument("--shop", default="demo shop", help="shop label")
    args = parser.parse_args(argv)

    days = max(1, min(args.days, 14))
    if args.out:
        base = Path(args.out).expanduser()
        base.mkdir(parents=True, exist_ok=True)
        tmp_note = f"using --out {base}"
    else:
        base = Path(tempfile.mkdtemp(prefix="omni-shop-weekly-"))
        tmp_note = f"using temp dir {base}"
    print(f"# SHOP WEEKLY DEMO ({tmp_note}, days={days}, shop={args.shop})\n")

    # 1. Demo folders.
    folders = build_demo_folders(base, days)
    for f in folders:
        print(f"  demo folder: {f}")

    # 2. Weekly trend.
    print("\n" + weekly_trend(folders, shop=args.shop))

    # 3. Multi-shop compare (each day as a pseudo-shop for the demo).
    shops = {f"shop-day-{i + 1:02d}": folder for i, folder in enumerate(folders)}
    print("\n" + multi_shop_compare(shops))

    # 4. Cron line for the morning ritual.
    out_base = base / "close_out"
    out_base.mkdir(parents=True, exist_ok=True)
    print("\n# CRON INSTALL (paste into `crontab -e`)\n")
    print(cron_install(folders[0], out_base, shop=args.shop))
    print("\n" + cron_install_help())

    # 5. Accountant pack for day-01.
    if _HAS_CLIENT:
        close = OmniOneClient.local().close(demo=False, folder=str(folders[0]), shop=args.shop)
    else:  # fallback: build directly from packs
        from omni_one.packs.seller_close import build_daily_close
        from omni_one.packs.seller_os import build_seller_briefing, ingest_seller_folder
        from omni_one.packs.seller_scenarios import run_all_scenarios

        events, _ = ingest_seller_folder(folders[0])
        close = build_daily_close(events, build_seller_briefing(events), run_all_scenarios(events), shop=args.shop)
    close_dir = base / "close_day_01"
    write_close_bundle(close, close_dir)
    zip_path = accountant_pack(close_dir)
    print(f"\n# ACCOUNTANT PACK\n  close_dir: {close_dir}\n  zip: {zip_path}")
    print(f"  contents: {accountant_pack_contents(zip_path)}")
    print(f"\nclose headline: {close['headline']}")
    print("\nDemo OK — every number above cites file:line (never stripped).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
