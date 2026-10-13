"""
Engine — deterministic data + ontology + operations layer
=========================================================
Built on efficient OSS: Python + DuckDB + Pandas + FastAPI + Pydantic
+ Tesseract + OpenCV + Matplotlib + local LLM mock (or Ollama).

Modules:

  foundry.py    (Datasets, Transforms, Lineage, Builds — DuckDB+Parquet, offline)
  ontology.py   (Object Types, Links, Actions — in-memory graph, offline)
  gotham.py     (Investigation graph, entity resolution — deterministic)
  aip.py        (Ontology-grounded logic — mock/Ollama, offline)
  apollo.py     (Deploy via Docker Compose)
  workshop.py   (Operations queue on the ontology)
  governance.py (Audit log, lineage, markings)

All pipelines reuse the deterministic 4-layer pipeline (core/data_processing_pipeline.py)
so LLM calls are bypassed for ~90% of data (local-first). E2E demo runs offline.
"""
