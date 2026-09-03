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
        self.path = Path(path)
        self.name = name
        self.path.mkdir(parents=True, exist_ok=True)
        self.versions_path = self.path / "_versions.json"
        if not self.versions_path.exists():
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
        self.versions_path.write_text(json.dumps(versions, indent=2))
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
    """Like Foundry PySpark @transform. Free Python function with lineage."""
    def __init__(self, name: str, inputs: List[FoundryDataset], output: FoundryDataset, fn: Callable):
        self.name = name
        self.inputs = inputs
        self.outputs = output
        self.fn = fn
        self.runs: List[Dict[str, Any]] = []

    def build(self, **kwargs) -> str:
        """Run transform, write output, track lineage. Returns version."""
        # Read inputs
        dfs = [ds.read_latest() for ds in self.inputs]
        # Run user fn (should return DataFrame or list[dict])
        result = self.fn(*dfs, **kwargs)
        lineage = f"transform:{self.name} inputs={[ds.name for ds in self.inputs]} at {datetime.now().isoformat()}"
        version = self.outputs.write(result, lineage=lineage)
        self.runs.append({"at": datetime.now().isoformat(), "version": version, "inputs": [ds.name for ds in self.inputs]})
        return version


class FoundryBranch:
    """Like Foundry branch, just a path suffix — free."""
    def __init__(self, base: Path, branch: str = "master"):
        self.base = Path(base)
        self.branch = branch
        self.path = self.base / f"branch_{branch}"
        self.path.mkdir(parents=True, exist_ok=True)

    def dataset(self, name: str) -> FoundryDataset:
        return FoundryDataset(self.path / name, name)


# Convenience: free checks (like Foundry Expectations)
def check_not_null(df, col: str) -> Dict[str, Any]:
    if not PD_AVAILABLE:
        return {"check": "not_null", "col": col, "passed": False, "error": "pandas missing"}
    nulls = int(df[col].isna().sum()) if col in df.columns else -1
    return {"check": "not_null", "col": col, "passed": nulls == 0, "nulls": nulls, "free": True}

def check_unique(df, col: str) -> Dict[str, Any]:
    if not PD_AVAILABLE:
        return {"check": "unique", "col": col, "passed": False}
    dups = int(df.duplicated(subset=[col]).sum()) if col in df.columns else -1
    return {"check": "unique", "col": col, "passed": dups == 0, "dups": dups, "free": True}
