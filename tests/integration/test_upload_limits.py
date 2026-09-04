"""Upload + traversal guards: oversize/corrupt/traversal rejected, inbox allowed."""
import tempfile
from pathlib import Path
import pytest


def test_upload_limits():
    from omni_one.infra.security import check_upload
    with pytest.raises(ValueError):
        check_upload("big.jpg", b"x" * (6 * 1024 * 1024), "image/jpeg", max_mb=5)
    with pytest.raises(ValueError):
        check_upload("evil.exe", b"x" * 100, "application/x-msdownload")
    with pytest.raises(ValueError):
        check_upload("corrupt.jpg", b"\xff\xd8" + b"NOT_AN_IMAGE" * 100, "image/jpeg", max_mb=5)
    # valid tiny png (1x1) passes
    tiny_png = bytes.fromhex("89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000d49444154789c626001000000ffff0300000600055bf0950000000049454e44ae426082")
    check_upload("ok.png", tiny_png, "image/png", max_mb=5)


def test_path_traversal_blocked(tmp_path=None):
    import tempfile
    from omni_one.infra.security import resolve_seller_folder
    with tempfile.TemporaryDirectory() as tmp:
        inbox = Path(tmp) / "inbox"
        inbox.mkdir()
        (inbox / "shopify_orders.csv").write_text("Order Name,Total\n#1,10\n")
        import os
        os.environ["ALLOWED_ROOT"] = str(inbox)
        # allowed
        assert resolve_seller_folder(str(inbox)).exists()
        # blocked: /etc, traversal
        import pytest as _pt
        with _pt.raises(ValueError):
            resolve_seller_folder("/etc")
        with _pt.raises(ValueError):
            resolve_seller_folder(str(inbox / ".." / "etc"))
        with _pt.raises(ValueError):
            resolve_seller_folder("/tmp/does-not-exist-omni-12345")
