"""Auto Close router tests: scan signals, plan selection, demo/empty/real runs."""
from pathlib import Path

from omni_one.packs.auto_close import run_auto, scan_folder, select_closes


def _biz_folder(tmp_path: Path) -> Path:
    d = tmp_path / "shop"
    d.mkdir()
    (d / "orders.csv").write_text("order,product,amount\n1,tote,45\n2,candle,22\n")
    (d / "receipt_001.png").write_bytes(bytes(200))
    (d / "reviews.csv").write_text("reviewer,stars,text\nAna,2,late delivery\nBob,5,great\n")
    (d / "stock.csv").write_text("sku,on_hand,velocity,unit_cost\nTOTE,10,2,12\n")
    (d / "refunds.csv").write_text("order_id,product,reason,amount\n1,tote,late,45\n")
    return d


def test_scan_finds_signals(tmp_path):
    inv = scan_folder(_biz_folder(tmp_path))
    assert inv["total_files"] == 5
    assert inv["photos"] == ["receipt_001.png"]
    assert "refunds.csv" in inv["signals"]["returns"]
    assert "reviews.csv" in inv["signals"]["reputation"]
    assert "stock.csv" in inv["signals"]["forecast"]


def test_plan_picks_right_closes(tmp_path):
    plan = select_closes(scan_folder(_biz_folder(tmp_path)))
    names = [p["close"] for p in plan]
    for expected in ["vision", "seller", "returns", "reputation", "forecast", "pipeline"]:
        assert expected in names, names
    assert names == sorted(names, key=names.index)  # deterministic order
    reasons = {p["close"]: p["reason"] for p in plan}
    assert "photo" in reasons["vision"]
    assert all(p["evidence"] for p in plan)


def test_plan_empty_folder_gets_seller_demo(tmp_path):
    e = tmp_path / "empty"
    e.mkdir()
    plan = select_closes(scan_folder(e))
    assert [p["close"] for p in plan] == ["seller"]
    assert "demo" in plan[0]["reason"]


def test_plan_deterministic(tmp_path):
    d = _biz_folder(tmp_path)
    assert select_closes(scan_folder(d)) == select_closes(scan_folder(d))


def test_run_auto_real_folder(tmp_path):
    s = run_auto(str(_biz_folder(tmp_path)), out=str(tmp_path / "auto"), seed=42)
    assert s["demo_mode"] is False
    assert set(s["ran"]) == {"vision", "seller", "returns", "reputation", "forecast", "pipeline"}
    assert "returns" in s["headlines"] and "$45.00" in s["headlines"]["returns"]
    assert (tmp_path / "auto" / "auto.json").exists()
    assert (tmp_path / "auto" / "AUTO.txt").exists()
    assert s["free"] is True
    assert len(s["do_today"]) > 0


def test_run_auto_empty_folder(tmp_path):
    e = tmp_path / "empty"
    e.mkdir()
    s = run_auto(str(e), out=str(tmp_path / "auto2"), seed=42)
    assert s["ran"] == ["seller"]
    assert s["headlines"]["seller"]  # demo fallback, never an error


def test_run_auto_demo_mode(tmp_path):
    s = run_auto(None, out=str(tmp_path / "auto3"), seed=42)
    assert s["demo_mode"] is True
    assert set(s["ran"]) == {"seller", "vision", "returns", "cashflow", "reputation", "forecast"}


def test_run_auto_deep_adds_ops(tmp_path):
    s = run_auto(str(_biz_folder(tmp_path)), out=str(tmp_path / "auto4"), seed=42, deep=True)
    assert "ops" in s["ran"]
    assert "pipeline" in s["ran"]


def test_run_auto_never_hard_fails(tmp_path):
    d = tmp_path / "weird"
    d.mkdir()
    (d / "binary.bin").write_bytes(bytes(range(256)))
    s = run_auto(str(d), out=str(tmp_path / "auto5"), seed=42)
    assert isinstance(s["ran"], list)  # completes, no exception
