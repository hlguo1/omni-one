# CLI

`omni-one` (after `pip install -e .`) or `PYTHONPATH=src python3 -m omni_one.cli ...`.

| Command | What |
|---|---|
| `omni-one doctor` | env + deps + pipeline smoke |
| `omni-one demo` | Seller demo briefing |
| `omni-one briefing --demo --json b.json` | briefing; `--folder /p` for real shop |
| `omni-one scenarios --demo` | 12 scenarios ranked |
| `omni-one operations` | full ontology→workshop→AIP→audit loop |
| `omni-one close --demo --out ./close_today` | **Daily Close bundle** (json/csv/reorder/replies/po) |
| `omni-one close --demo --locale es` | same numbers, Spanish drafts (`en\|es\|zh\|fr\|de`) |
| `omni-one export --demo --out briefing.csv` | briefing CSV |
| `omni-one serve --port 5003` | API server |
| `omni-one evaluate --n 500` | eval harness |

`make demo|close|test|e2e|serve|docker|lint|doctor` wraps the same.
