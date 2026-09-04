"""
Foundry — Free alternative to Palantir Foundry
=============================================
Palantir Foundry: $1-5M/yr for data integration, transforms, lineage, builds.
Free alternative: DuckDB + Pandas + Parquet + Python — same power, $0.

Concepts mirrored:
  Dataset  — versioned Parquet folder (like Foundry dataset)
  Transform — Python function with inputs/outputs, lineage tracked (like PySpark transform)
  Build    — incremental run with checks, backed by DuckDB (free Spark alternative)
  Branch   — like Foundry branches, just a folder suffix
  Checks   — deterministic data quality, like Foundry Expectations

Tech: cheapest efficient:
  - DuckDB 1.5.5 (free, in-process OLAP, 10x faster than Spark for <100GB)
  - Pandas 2.x (free, ETL)
  - Parquet (free, columnar, compressed)
  - Nothing else.

Use: Foundry datasets feed Ontology objects (free digital twin).
"""
from __future__ import annotations
import shutil
from pathlib import Path
from typing import List, Dict, Any, Callable, Optional
from datetime import datetime
import hashlib
import json

try:
    import duckdb  # type: ignore
    DUCK_AVAILABLE = True
except ImportError:
    duckdb = None  # type: ignore
    DUCK_AVAILABLE = False

try:
    import pandas as pd  # type: ignore
    PD_AVAILABLE = True
except ImportError:
    pd = None  # type: ignore
    PD_AVAILABLE = False


class FoundryDataset:
    """Versioned dataset, like Foundry dataset. Parquet on disk, free."""
    def __init__(self, path: Path, name: str):
        from threading import RLock as _RL
        self._lock = _RL()
        self.path = Path(path)
        self.name = name
        self.path.mkdir(parents=True, exist_ok=True)
        self.versions_path = self.path / "_versions.json"
        if not self.versions_path.exists():
            try:
                from ..infra.store import atomic_write_text as _atomic
            except Exception:
                try:
                    from omni_one.infra.store import atomic_write_text as _atomic  # type: ignore
                except Exception:
                    _atomic = None  # type: ignore
            if _atomic is not None:
                _atomic(self.versions_path, json.dumps([]))
            else:
                self.versions_path.write_text(json.dumps([]))

    def write(self, df, lineage: str):
        """Write new version (like Foundry transaction). df is pandas DataFrame or list[dict]. Free: Parquet if pyarrow else CSV."""
        if not PD_AVAILABLE:
            raise RuntimeError("pandas not installed: pip install pandas (free)")
        if isinstance(df, list):
            df = pd.DataFrame(df)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        version = f"v{ts}_{hashlib.sha256(lineage.encode()).hexdigest()[:6]}"
        # Try parquet, fallback to csv (both free, parquet preferred)
        part = self.path / f"{version}.parquet"
        try:
            df.to_parquet(part, index=False)
            latest = self.path / "latest.parquet"
            try:
                shutil.copy(part, latest)
            except Exception:
                df.to_parquet(latest, index=False)
        except Exception:
            # Fallback free: CSV (no pyarrow needed)
            part = self.path / f"{version}.csv"
            df.to_csv(part, index=False)
            latest = self.path / "latest.csv"
            df.to_csv(latest, index=False)
        versions = json.loads(self.versions_path.read_text())
        versions.append({"version": version, "lineage": lineage, "at": datetime.now().isoformat(), "rows": len(df), "path": str(part.name)})
        # Atomic versions write (crash-safe)
        try:
            from ..infra.store import atomic_write_text as _atomic2
        except Exception:
            try:
                from omni_one.infra.store import atomic_write_text as _atomic2  # type: ignore
            except Exception:
                _atomic2 = None  # type: ignore
        blob = json.dumps(versions, indent=2)
        with self._lock:
            if _atomic2 is not None:
                _atomic2(self.versions_path, blob)
            else:
                import os as _os, tempfile as _tf
                fd, tmp = _tf.mkstemp(dir=str(self.path), prefix="_versions.json.tmp.")
                try:
                    with _os.fdopen(fd, "w", encoding="utf-8") as f:
                        f.write(blob)
                    _os.replace(tmp, self.versions_path)
                finally:
                    try:
                        if _os.path.exists(tmp):
                            _os.unlink(tmp)
                    except Exception:
                        pass
        return version

    def read_latest(self):
        if not PD_AVAILABLE:
            raise RuntimeError("pandas required")
        # Prefer parquet, fallback to csv (free)
        for latest_name in ["latest.parquet", "latest.csv"]:
            latest = self.path / latest_name
            if latest.exists():
                try:
                    if latest.suffix == ".parquet":
                        try:
                            return pd.read_parquet(latest)
                        except Exception:
                            if DUCK_AVAILABLE:
                                con = duckdb.connect(":memory:")
                                return con.execute(f"SELECT * FROM read_parquet('{latest}')").fetchdf()
                            raise
                    else:
                        return pd.read_csv(latest)
                except Exception:
                    continue
        return pd.DataFrame()

    def query(self, sql: str):
        """Free query via DuckDB, like Foundry Spark SQL but cheaper."""
        if not DUCK_AVAILABLE:
            # Fallback pandas query (limited)
            df = self.read_latest()
            # Support simple sql like "SELECT * WHERE x > 5" — not full, just for demo
            raise RuntimeError("DuckDB not installed: pip install duckdb (free) for SQL")
        con = duckdb.connect(":memory:")
        latest = self.path / "latest.parquet"
        # Replace dataset name with parquet path for demo
        # User writes SQL against `dataset` alias; we expose as `t`
        con.execute(f"CREATE VIEW t AS SELECT * FROM read_parquet('{latest}')")
        return con.execute(sql.replace(self.name, "t").replace("dataset", "t")).fetchdf()

    def versions(self) -> List[Dict[str, Any]]:
        return json.loads(self.versions_path.read_text())

    def lineage(self) -> str:
        versions = self.versions()
        if not versions:
            return "empty"
        return versions[-1]["lineage"]


class Transform:
    """Like Foundry PySpark @transform. Free Python function with lineage + expectations gate."""
    def __init__(self, name: str, inputs: List[FoundryDataset], output: FoundryDataset, fn: Callable,
                 expectations: Optional[List[Callable]] = None, incremental: bool = False):
        self.name = name
        self.inputs = inputs
        self.outputs = output
        self.fn = fn
        self.expectations = expectations or []  # each fn(df) -> {"passed": bool, ...}
        self.incremental = incremental
        self.runs: List[Dict[str, Any]] = []

    def _inputs_fingerprint(self) -> str:
        try:
            parts = []
            for ds in self.inputs:
                vers = ds.versions()
                parts.append(f"{ds.name}:{vers[-1]['version'] if vers else 'empty'}:{vers[-1]['rows'] if vers else 0}")
            return hashlib.sha256("|".join(parts).encode()).hexdigest()[:12]
        except Exception:
            return "unknown"

    def build(self, **kwargs) -> str:
        """Run transform, gate on expectations, track lineage. Returns version."""
        fp_before = self._inputs_fingerprint()
        dfs = [ds.read_latest() for ds in self.inputs]
        result = self.fn(*dfs, **kwargs)
        if isinstance(result, list) and PD_AVAILABLE:
            import pandas as _pd
            result_df = _pd.DataFrame(result)
        else:
            result_df = result
        check_results = []
        for exp in self.expectations:
            try:
                cr = exp(result_df)
                check_results.append(cr)
                if isinstance(cr, dict) and cr.get("passed") is False:
                    raise ValueError(f"Expectation failed: {cr}")
            except ValueError:
                raise
            except Exception as e:
                check_results.append({"passed": False, "error": str(e)})
                raise ValueError(f"Expectation error: {e}")
        lineage = f"transform:{self.name} inputs={[ds.name for ds in self.inputs]} fp={fp_before} at {datetime.now().isoformat()}"
        version = self.outputs.write(result_df, lineage=lineage)
        self.runs.append({"at": datetime.now().isoformat(), "version": version, "inputs": [ds.name for ds in self.inputs], "checks": check_results, "inputs_fp": fp_before})
        return version

    def build_if_stale(self, **kwargs) -> Optional[str]:
        """Incremental: skip if inputs fingerprint unchanged since last run. Free."""
        fp = self._inputs_fingerprint()
        if self.runs and self.runs[-1].get("inputs_fp") == fp:
            return None  # fresh, skip
        return self.build(**kwargs)


class FoundryBranch:
    """Like Foundry branch, just a path suffix — free."""
    def __init__(self, base: Path, branch: str = "master"):
        self.base = Path(base)
        self.branch = branch
        self.path = self.base / f"branch_{branch}"
        self.path.mkdir(parents=True, exist_ok=True)

    def dataset(self, name: str) -> FoundryDataset:
        return FoundryDataset(self.path / name, name)


# Convenience: free checks (like Foundry Expectations) + profiling + multi-SQL
def check_not_null(df, col: str) -> Dict[str, Any]:
    if not PD_AVAILABLE:
        return {"check": "not_null", "col": col, "passed": False, "error": "pandas missing"}
    if col not in df.columns:
        return {"check": "not_null", "col": col, "passed": False, "error": f"missing column {col}"}
    nulls = int(df[col].isna().sum())
    return {"check": "not_null", "col": col, "passed": nulls == 0, "nulls": nulls, "rows": len(df), "free": True}

def check_unique(df, col: str) -> Dict[str, Any]:
    if not PD_AVAILABLE:
        return {"check": "unique", "col": col, "passed": False}
    if col not in df.columns:
        return {"check": "unique", "col": col, "passed": False, "error": f"missing column {col}"}
    dups = int(df.duplicated(subset=[col]).sum())
    return {"check": "unique", "col": col, "passed": dups == 0, "dups": dups, "rows": len(df), "free": True}

def check_range(df, col: str, min_v: Optional[float] = None, max_v: Optional[float] = None) -> Dict[str, Any]:
    if not PD_AVAILABLE or col not in df.columns:
        return {"check": "range", "col": col, "passed": False}
    try:
        s = df[col].dropna().astype(float)
        ok = True
        if min_v is not None and (s < min_v).any(): ok = False
        if max_v is not None and (s > max_v).any(): ok = False
        return {"check": "range", "col": col, "passed": ok, "min": float(s.min()) if len(s) else None, "max": float(s.max()) if len(s) else None, "free": True}
    except Exception as e:
        return {"check": "range", "col": col, "passed": False, "error": str(e)}

def profile_dataset(df) -> Dict[str, Any]:
    """Free dataset profile (like Foundry stats): rows, cols, nulls, numeric summary. No Spark."""
    if not PD_AVAILABLE:
        return {"error": "pandas missing"}
    try:
        prof = {"rows": len(df), "cols": list(df.columns), "free": True, "columns": {}}
        for c in df.columns:
            s = df[c]
            prof["columns"][c] = {"nulls": int(s.isna().sum()), "unique": int(s.nunique(dropna=True))}
            try:
                num = s.dropna().astype(float)
                prof["columns"][c].update({"min": float(num.min()), "max": float(num.max()), "mean": float(num.mean())})
            except Exception:
                # top values for categorical
                try:
                    prof["columns"][c]["top"] = s.value_counts(dropna=True).head(3).to_dict()
                except Exception:
                    pass
        return prof
    except Exception as e:
        return {"error": str(e)}

def sql_join(datasets: Dict[str, Any], sql: str):
    """Multi-dataset SQL via DuckDB (free). datasets: {alias: FoundryDataset}. SQL references aliases."""
    if not DUCK_AVAILABLE:
        raise RuntimeError("DuckDB not installed: pip install duckdb (free)")
    con = duckdb.connect(":memory:")
    for alias, ds in datasets.items():
        # Support both FoundryDataset and DataFrame
        try:
            if hasattr(ds, "path"):
                latest = None
                for cand in ["latest.parquet", "latest.csv"]:
                    p = ds.path / cand
                    if p.exists():
                        latest = p
                        break
                if latest is None:
                    continue
                if latest.suffix == ".parquet":
                    con.execute(f"CREATE VIEW {alias} AS SELECT * FROM read_parquet('{latest}')")
                else:
                    con.execute(f"CREATE VIEW {alias} AS SELECT * FROM read_csv('{latest}', header=true)")
            else:
                con.register(alias, ds)
        except Exception as e:
            raise RuntimeError(f"register {alias}: {e}")
    return con.execute(sql).fetchdf()
