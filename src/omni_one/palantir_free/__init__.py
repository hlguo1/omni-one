"""
Palantir-Free — The free alternative to Palantir Foundry/Gotham/AIP/Apollo
==========================================================================
Built on cheapest efficient OSS: Python + DuckDB + Pandas + FastAPI + Pydantic
+ Tesseract + OpenCV + Matplotlib + local LLM mock (or Ollama).

This package mirrors Palantir's pillars with 0 cloud fees:

  Palantir Foundry  →  foundry.py   (Datasets, Transforms, Lineage, Builds — DuckDB+Parquet, free)
  Palantir Ontology →  ontology.py  (Object Types, Links, Actions — in-memory graph, free)
  Palantir Gotham   →  gotham.py    (Investigation graph, entity res — free)
  Palantir AIP      →  aip.py       (Ontology-grounded LLM logic — free mock/Ollama)
  Palantir Apollo   →  apollo.py    (Deploy via Docker Compose — free)

All pipelines reuse the deterministic 4-layer pipeline (core/data_processing_pipeline.py)
so LLM costs are 0 for 90% of data (Local first). Total cost for e2e demo: $0.00.
"""
