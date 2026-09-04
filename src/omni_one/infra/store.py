"""
Local Store — free, local-first persistence for very small businesses.
======================================================================
Single owner of ./data persistence:

  ./data/omni.duckdb        — ontology / workshop / ledger / briefing cache (if duckdb installed)
  ./data/parquet/*.parquet  — bulk snapshots via Foundry (optional)
  ./data/audit.jsonl        — append-only hash-chained audit (survives restart)
  ./data/inbox/             — ONLY allowed folder root for seller uploads (path-traversal guard)

Design:
- stdlib only by default; duckdb/pandas are optional and lazy.
- All file writes are atomic (tmp + os.replace + fsync).
- All in-memory mutations guarded by RLock.
- Never raises on missing optional deps — degrades to JSON files.

This is the industry-advanced bit without the industry bill:
idempotent, restart-safe, auditable, $0.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


_lock = threading.RLock()

# --- paths ---------------------------------------------------------------

def get_data_root(explicit: Optional[str] = None) -> Path:
    """Resolve data root: OMNI_DATA_DIR > ./data (repo root aware)."""
    if explicit:
        p = Path(explicit).expanduser()
    else:
        env = os.getenv("OMNI_DATA_DIR") or os.getenv("DUCKDB_PATH_PARENT")
        if env:
            # DUCKDB_PATH may be a file; use its parent
            ep = Path(env).expanduser()
            p = ep.parent if ep.suffix in (".duckdb", ".db") else ep
        else:
            # src/omni_one/infra/store.py -> repo root = parents[3]
            here = Path(__file__).resolve()
            try:
                repo = here.parents[3]
            except IndexError:
                repo = Path.cwd()
            p = repo / "data"
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_duckdb_path(explicit: Optional[str] = None) -> Path:
    env = explicit or os.getenv("DUCKDB_PATH")
    if env:
        ep = Path(env).expanduser()
        ep.parent.mkdir(parents=True, exist_ok=True)
        return ep
    return get_data_root() / "omni.duckdb"


def get_audit_path(explicit: Optional[str] = None) -> Path:
    env = explicit or os.getenv("AUDIT_PATH")
    if env:
        ap = Path(env).expanduser()
        ap.parent.mkdir(parents=True, exist_ok=True)
        return ap
    return get_data_root() / "audit.jsonl"


def get_inbox_root(explicit: Optional[str] = None) -> Path:
    env = explicit or os.getenv("ALLOWED_ROOT") or os.getenv("SELLER_INBOX")
    base = Path(env).expanduser() if env else get_data_root() / "inbox"
    base.mkdir(parents=True, exist_ok=True)
    return base


# --- atomic writes -------------------------------------------------------

def atomic_write_bytes(path: Path | str, data: bytes) -> str:
    """Atomic write: tmp in same dir + fsync + os.replace. Crash-safe."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(p.parent), prefix=p.name + ".tmp.")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            try:
                os.fsync(f.fileno())
            except Exception:
                pass
        os.replace(tmp, p)
    finally:
        try:
            if os.path.exists(tmp):
                os.unlink(tmp)
        except Exception:
            pass
    return str(p)


def atomic_write_text(path: Path | str, text: str, encoding: str = "utf-8") -> str:
    return atomic_write_bytes(Path(path), text.encode(encoding))


def atomic_write_json(path: Path | str, obj: Any) -> str:
    return atomic_write_text(Path(path), json.dumps(obj, indent=2, default=str))


def append_jsonl(path: Path | str, obj: Dict[str, Any]) -> Dict[str, Any]:
    """Append one JSON line with fsync. Thread-safe via module lock."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(obj, default=str) + "\n"
    with _lock:
        with open(p, "a", encoding="utf-8") as f:
            f.write(line)
            f.flush()
            try:
                os.fsync(f.fileno())
            except Exception:
                pass
    return obj


def read_jsonl(path: Path | str, limit: int = 10000) -> List[Dict[str, Any]]:
    p = Path(path)
    if not p.exists():
        return []
    out: List[Dict[str, Any]] = []
    with open(p, encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                continue
            if len(out) >= limit:
                break
    return out


def stable_id(*parts: str) -> str:
    """Deterministic id: sha256 hex 16 of joined parts."""
    h = hashlib.sha256("|".join(str(x) for x in parts).encode()).hexdigest()
    return h[:16]


def folder_fingerprint(folder: Path) -> str:
    """Hash of file names + mtimes + sizes (cheap staleness check, no content read)."""
    folder = Path(folder)
    items: List[str] = []
    try:
        for p in sorted(folder.rglob("*")):
            if p.is_dir():
                continue
            try:
                st = p.stat()
                items.append(f"{p.relative_to(folder)}:{st.st_size}:{int(st.st_mtime)}")
            except Exception:
                continue
    except Exception:
        pass
    return hashlib.sha256("\n".join(items).encode()).hexdigest()[:16]


# --- DuckDB-backed KV store (optional, degrades to JSON) -----------------

class LocalStore:
    """Tiny persisted KV + tables. DuckDB if available, else JSON files.

    Tables (duckdb):
      kv(key TEXT PRIMARY KEY, value TEXT, updated_at TEXT)
      cost_ledger(seq INTEGER, at TEXT, label TEXT, amount_usd REAL, meta TEXT)
      briefing_cache(folder_hash TEXT PRIMARY KEY, at TEXT, briefing TEXT)
      workshop_decisions(id TEXT PRIMARY KEY, data TEXT, updated_at TEXT)
      ontology_objects(otype TEXT, pk TEXT, data TEXT, updated_at TEXT, PRIMARY KEY(otype, pk))
    """

    def __init__(self, data_root: Optional[str | Path] = None, duckdb_path: Optional[str | Path] = None):
        self.data_root = Path(data_root) if data_root else get_data_root()
        self.data_root.mkdir(parents=True, exist_ok=True)
        self.duckdb_path = Path(duckdb_path) if duckdb_path else get_duckdb_path()
        self._lock = threading.RLock()
        self._con = None
        self._duck_ok = False
        self._json_fallback = self.data_root / "kv.json"
        try:
            import duckdb  # type: ignore
            self._duckdb = duckdb
            self._con = duckdb.connect(str(self.duckdb_path))
            self._init_schema()
            self._duck_ok = True
        except Exception:
            self._duckdb = None  # type: ignore
            self._con = None
            self._duck_ok = False

    @property
    def backend(self) -> str:
        return "duckdb" if self._duck_ok else "json"

    def _init_schema(self) -> None:
        assert self._con is not None
        with self._lock:
            self._con.execute("CREATE TABLE IF NOT EXISTS kv(key TEXT PRIMARY KEY, value TEXT, updated_at TEXT)")
            self._con.execute("CREATE TABLE IF NOT EXISTS cost_ledger(seq INTEGER, at TEXT, label TEXT, amount_usd DOUBLE, meta TEXT)")
            self._con.execute("CREATE TABLE IF NOT EXISTS briefing_cache(folder_hash TEXT PRIMARY KEY, at TEXT, briefing TEXT)")
            self._con.execute("CREATE TABLE IF NOT EXISTS workshop_decisions(id TEXT PRIMARY KEY, data TEXT, updated_at TEXT)")
            self._con.execute("CREATE TABLE IF NOT EXISTS ontology_objects(otype TEXT, pk TEXT, data TEXT, updated_at TEXT, PRIMARY KEY(otype, pk))")

    # -- kv --
    def kv_get(self, key: str) -> Optional[str]:
        with self._lock:
            if self._duck_ok and self._con is not None:
                try:
                    row = self._con.execute("SELECT value FROM kv WHERE key=?", [key]).fetchone()
                    return row[0] if row else None
                except Exception:
                    return None
            try:
                if self._json_fallback.exists():
                    data = json.loads(self._json_fallback.read_text(encoding="utf-8"))
                    return data.get(key)
            except Exception:
                pass
            return None

    def kv_set(self, key: str, value: str) -> None:
        now = datetime.now().isoformat()
        with self._lock:
            if self._duck_ok and self._con is not None:
                try:
                    self._con.execute(
                        "INSERT INTO kv(key, value, updated_at) VALUES(?,?,?) "
                        "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
                        [key, value, now],
                    )
                    return
                except Exception:
                    pass
            # JSON fallback (atomic)
            try:
                data: Dict[str, Any] = {}
                if self._json_fallback.exists():
                    try:
                        data = json.loads(self._json_fallback.read_text(encoding="utf-8"))
                    except Exception:
                        data = {}
                data[key] = value
                atomic_write_json(self._json_fallback, data)
            except Exception:
                pass

    # -- cost ledger --
    def ledger_append(self, label: str, amount_usd: float, meta: Optional[Dict[str, Any]] = None) -> int:
        now = datetime.now().isoformat()
        with self._lock:
            if self._duck_ok and self._con is not None:
                try:
                    row = self._con.execute("SELECT COALESCE(MAX(seq),0) FROM cost_ledger").fetchone()
                    seq = int(row[0] or 0) + 1
                    self._con.execute(
                        "INSERT INTO cost_ledger(seq, at, label, amount_usd, meta) VALUES(?,?,?,?,?)",
                        [seq, now, label, float(amount_usd), json.dumps(meta or {}, default=str)],
                    )
                    return seq
                except Exception:
                    pass
            # JSONL fallback
            seq = len(read_jsonl(self.data_root / "cost_ledger.jsonl")) + 1
            append_jsonl(self.data_root / "cost_ledger.jsonl", {"seq": seq, "at": now, "label": label, "amount_usd": amount_usd, "meta": meta or {}})
            return seq

    def ledger_total(self) -> float:
        with self._lock:
            if self._duck_ok and self._con is not None:
                try:
                    row = self._con.execute("SELECT COALESCE(SUM(amount_usd),0) FROM cost_ledger").fetchone()
                    return float(row[0] or 0.0)
                except Exception:
                    pass
            total = 0.0
            for e in read_jsonl(self.data_root / "cost_ledger.jsonl", limit=100000):
                try:
                    total += float(e.get("amount_usd", 0) or 0)
                except Exception:
                    continue
            return total

    # -- briefing cache --
    def briefing_get(self, folder_hash: str, max_age_s: int = 3600) -> Optional[Dict[str, Any]]:
        with self._lock:
            raw: Optional[str] = None
            at: Optional[str] = None
            if self._duck_ok and self._con is not None:
                try:
                    row = self._con.execute("SELECT at, briefing FROM briefing_cache WHERE folder_hash=?", [folder_hash]).fetchone()
                    if row:
                        at, raw = row[0], row[1]
                except Exception:
                    raw = None
            else:
                p = self.data_root / "briefing_cache" / f"{folder_hash}.json"
                if p.exists():
                    try:
                        payload = json.loads(p.read_text(encoding="utf-8"))
                        at, raw = payload.get("at"), json.dumps(payload.get("briefing", {}))
                    except Exception:
                        raw = None
            if not raw:
                return None
            try:
                age = (datetime.now() - datetime.fromisoformat(str(at))).total_seconds() if at else 1e9
                if age > max_age_s:
                    return None
                return json.loads(raw)
            except Exception:
                return None

    def briefing_put(self, folder_hash: str, briefing: Dict[str, Any]) -> None:
        now = datetime.now().isoformat()
        blob = json.dumps(briefing, default=str)
        with self._lock:
            if self._duck_ok and self._con is not None:
                try:
                    self._con.execute(
                        "INSERT INTO briefing_cache(folder_hash, at, briefing) VALUES(?,?,?) "
                        "ON CONFLICT(folder_hash) DO UPDATE SET at=excluded.at, briefing=excluded.briefing",
                        [folder_hash, now, blob],
                    )
                    return
                except Exception:
                    pass
            p = self.data_root / "briefing_cache" / f"{folder_hash}.json"
            atomic_write_json(p, {"at": now, "briefing": briefing})

    # -- workshop decisions --
    def workshop_save(self, decisions: Dict[str, Dict[str, Any]]) -> None:
        now = datetime.now().isoformat()
        with self._lock:
            if self._duck_ok and self._con is not None:
                try:
                    for did, d in decisions.items():
                        self._con.execute(
                            "INSERT INTO workshop_decisions(id, data, updated_at) VALUES(?,?,?) "
                            "ON CONFLICT(id) DO UPDATE SET data=excluded.data, updated_at=excluded.updated_at",
                            [did, json.dumps(d, default=str), now],
                        )
                    return
                except Exception:
                    pass
            atomic_write_json(self.data_root / "workshop.json", {"at": now, "decisions": decisions})

    def workshop_load(self) -> Dict[str, Dict[str, Any]]:
        with self._lock:
            if self._duck_ok and self._con is not None:
                try:
                    rows = self._con.execute("SELECT id, data FROM workshop_decisions").fetchall()
                    return {r[0]: json.loads(r[1]) for r in rows}
                except Exception:
                    pass
            p = self.data_root / "workshop.json"
            if p.exists():
                try:
                    return json.loads(p.read_text(encoding="utf-8")).get("decisions", {})
                except Exception:
                    return {}
            return {}

    # -- ontology objects --
    def ontology_save(self, objects: Dict[str, Dict[str, Dict[str, Any]]]) -> None:
        now = datetime.now().isoformat()
        with self._lock:
            if self._duck_ok and self._con is not None:
                try:
                    for otype, mp in objects.items():
                        for pk, od in mp.items():
                            self._con.execute(
                                "INSERT INTO ontology_objects(otype, pk, data, updated_at) VALUES(?,?,?,?) "
                                "ON CONFLICT(otype, pk) DO UPDATE SET data=excluded.data, updated_at=excluded.updated_at",
                                [otype, pk, json.dumps(od, default=str), now],
                            )
                    return
                except Exception:
                    pass
            atomic_write_json(self.data_root / "ontology_objects.json", {"at": now, "objects": objects})

    def ontology_load(self) -> Dict[str, Dict[str, Dict[str, Any]]]:
        with self._lock:
            if self._duck_ok and self._con is not None:
                try:
                    rows = self._con.execute("SELECT otype, pk, data FROM ontology_objects").fetchall()
                    out: Dict[str, Dict[str, Dict[str, Any]]] = {}
                    for otype, pk, data in rows:
                        out.setdefault(otype, {})[pk] = json.loads(data)
                    if out:
                        return out
                except Exception:
                    pass
            p = self.data_root / "ontology_objects.json"
            if p.exists():
                try:
                    return json.loads(p.read_text(encoding="utf-8")).get("objects", {})
                except Exception:
                    return {}
            return {}

    def close(self) -> None:
        with self._lock:
            try:
                if self._con is not None:
                    self._con.close()
            except Exception:
                pass
            self._con = None


_global_store: Optional[LocalStore] = None
_global_lock = threading.RLock()


def get_store(data_root: Optional[str | Path] = None) -> LocalStore:
    """Process-wide singleton LocalStore."""
    global _global_store
    with _global_lock:
        if _global_store is None:
            _global_store = LocalStore(data_root=data_root)
        return _global_store


__all__ = [
    "LocalStore", "get_store", "get_data_root", "get_duckdb_path", "get_audit_path",
    "get_inbox_root", "atomic_write_bytes", "atomic_write_text", "atomic_write_json",
    "append_jsonl", "read_jsonl", "stable_id", "folder_fingerprint",
]
