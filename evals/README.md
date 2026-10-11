# Evals — prove the Close stays honest

- `evals/generate.py --shops N --out DIR --seed S` — deterministic N-shop corpus
  (archetypes: golden_demo/standard/refunds-only/single-SKU/empty/unicode/semicolon/BOM/stress_10k).
- `evals/run.py --corpus DIR --out RES` — ingest→briefing→scenarios→close per shop,
  5 invariants + idempotency, golden profit 169.09±0.05, `summary.csv` + table.
- `evals/corpus/` — 6 checked-in shops (<1.5MB). `evals/corpus_big/` — 80 shops + manifest.
- Property/fuzz/contract: `test_property_close test_fuzz_parsers test_contract_close`.
- Corpus gate: `test_corpus_big_verify` (80 shops ingest, manifest GMV match, archetypes).
