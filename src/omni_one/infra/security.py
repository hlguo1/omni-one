"""
Security helpers — free, no extra deps.
=======================================
- Path-traversal guard: seller folders must resolve inside ALLOWED_ROOT (./data/inbox) or /tmp demo.
- Upload guard: size + MIME + Pillow verify (no malicious payloads).
- Tiny in-memory rate limiter (no Redis needed for 1-5 person shops).
- Admin auth dependency (API key required for /admin/*).
"""
from __future__ import annotations

import os
import time
import threading
from collections import defaultdict, deque
from pathlib import Path
from typing import Optional


def get_allowed_roots() -> list[Path]:
    roots: list[Path] = []
    for env in ("ALLOWED_ROOT", "SELLER_INBOX", "OMNI_DATA_DIR"):
        v = os.getenv(env)
        if v:
            try:
                p = Path(v).expanduser().resolve()
                roots.append(p)
                # If DUCKDB_PATH file given, allow its parent too
                if p.suffix in (".duckdb", ".db"):
                    roots.append(p.parent)
            except Exception:
                continue
    # Defaults: ./data/inbox + /tmp (demo) + cwd/data/inbox
    try:
        from .store import get_inbox_root  # type: ignore
        roots.append(get_inbox_root().resolve())
    except Exception:
        pass
    for cand in (Path("/tmp"), Path.cwd() / "data" / "inbox", Path("./data/inbox")):
        try:
            cand.mkdir(parents=True, exist_ok=True)
            roots.append(cand.resolve())
        except Exception:
            continue
    # de-dup preserving order
    seen: set[str] = set()
    out: list[Path] = []
    for r in roots:
        s = str(r)
        if s not in seen:
            seen.add(s)
            out.append(r)
    return out


def resolve_seller_folder(folder: str | Path, allow_tmp_demo: bool = True) -> Path:
    """Validate seller folder param. Raises ValueError on traversal / missing / outside roots.

    Allows: ALLOWED_ROOT (./data/inbox), /tmp/* (demo convenience).
    Rejects: .. escapes, /etc, /Users/* outside inbox, non-existent.
    """
    if not folder:
        raise ValueError("folder is required (or use demo:true)")
    p = Path(str(folder)).expanduser()
    try:
        resolved = p.resolve()
    except Exception:
        raise ValueError(f"Invalid folder: {folder}")
    if not resolved.exists() or not resolved.is_dir():
        raise ValueError(f"Folder not found: {folder}")
    # Block obvious sensitive roots
    blocked_prefixes = ("/etc", "/var/root", "/root", "/proc", "/sys")
    rs = str(resolved)
    for b in blocked_prefixes:
        if rs == b or rs.startswith(b + "/"):
            raise ValueError(f"Folder not allowed: {folder}")
    allowed = get_allowed_roots()
    # Also allow any /tmp subdir for demo convenience (shops drag ~/Downloads -> /tmp/my_shop)
    if allow_tmp_demo and (rs == "/tmp" or rs.startswith("/tmp/")):
        return resolved
    for root in allowed:
        try:
            if resolved == root or resolved.is_relative_to(root):  # py3.9+
                return resolved
        except AttributeError:
            # py3.8 fallback
            try:
                resolved.relative_to(root)
                return resolved
            except Exception:
                continue
        except Exception:
            continue
    raise ValueError(
        f"Folder not allowed: {folder}. Copy your shop files into ./data/inbox/ "
        f"or /tmp/my_shop/ (allowed: {[str(r) for r in allowed][:4]})"
    )


ALLOWED_IMAGE_MIME = {"image/jpeg", "image/png", "image/webp", "image/jpg", "application/pdf"}
ALLOWED_IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".pdf"}


def check_upload(filename: str, data: bytes, content_type: Optional[str] = None, max_mb: int = 5) -> None:
    """Raise ValueError on oversize / bad type / corrupt image. Free."""
    if not data or len(data) < 10:
        raise ValueError("Empty file")
    max_bytes = int(max_mb) * 1024 * 1024
    if len(data) > max_bytes:
        raise ValueError(f"File too large ({len(data)} bytes, max {max_mb}MB)")
    ext = Path(filename or "").suffix.lower()
    if ext and ext not in ALLOWED_IMAGE_EXT and ext != ".txt":
        raise ValueError(f"Unsupported file type {ext} (allowed jpg/png/webp/pdf)")
    if content_type and content_type not in ALLOWED_IMAGE_MIME and not content_type.startswith("multipart/") and content_type != "application/octet-stream":
        # Be lenient: browsers send image/jpeg etc; only hard-block executables
        if content_type.startswith(("application/x-", "text/html", "application/javascript")):
            raise ValueError(f"Unsupported content-type {content_type}")
    # Pillow verify for images (skips pdf/txt)
    if ext in {".jpg", ".jpeg", ".png", ".webp"} and len(data) >= 100:
        try:
            from PIL import Image  # type: ignore
            import io as _io
            im = Image.open(_io.BytesIO(data))
            im.verify()
        except ImportError:
            pass  # Pillow optional in minimal env — skip verify
        except Exception as e:
            raise ValueError(f"Corrupt image: {e}")


class RateLimiter:
    """Fixed-window in-memory rate limiter. Thread-safe. No Redis."""

    def __init__(self, max_requests: int = 60, window_s: int = 60):
        self.max_requests = max_requests
        self.window_s = window_s
        self._lock = threading.RLock()
        self._hits: dict[str, deque] = defaultdict(deque)

    def allow(self, key: str) -> bool:
        now = time.time()
        with self._lock:
            q = self._hits[key]
            while q and now - q[0] > self.window_s:
                q.popleft()
            if len(q) >= self.max_requests:
                return False
            q.append(now)
            return True

    def retry_after(self, key: str) -> int:
        with self._lock:
            q = self._hits.get(key)
            if not q:
                return 0
            return max(0, int(self.window_s - (time.time() - q[0])))


_global_limiter: Optional[RateLimiter] = None
_limiter_lock = threading.RLock()


def get_rate_limiter() -> RateLimiter:
    global _global_limiter
    with _limiter_lock:
        if _global_limiter is None:
            try:
                rpm = int(os.getenv("SELLER_PHOTO_RPM", "60"))
            except Exception:
                rpm = 60
            _global_limiter = RateLimiter(max_requests=rpm, window_s=60)
        return _global_limiter


def valid_api_keys() -> list[str]:
    raw = os.getenv("VALID_API_KEYS", "")
    if raw.strip():
        return [k.strip() for k in raw.split(",") if k.strip()]
    # Fallback defaults (dev convenience; prod must set VALID_API_KEYS — see settings validator)
    return ["demo-key", "test-key"]


def is_valid_key(key: Optional[str]) -> bool:
    if not key:
        return False
    return key.strip() in set(valid_api_keys())


__all__ = [
    "get_allowed_roots", "resolve_seller_folder", "check_upload",
    "RateLimiter", "get_rate_limiter", "valid_api_keys", "is_valid_key",
    "ALLOWED_IMAGE_MIME", "ALLOWED_IMAGE_EXT",
]
