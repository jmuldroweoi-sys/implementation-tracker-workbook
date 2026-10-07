# Exports

All files in this folder are synthetic data, generated from the workbook tables by `python tools/build_workbook.py --exports` after headless recalculation. They are never edited by hand.

| Folder | Contents |
|---|---|
| `csv/` | One CSV per exported table, with the columns listed in `config/export-map.yaml` |
| `jsonl/` | `Event-Log.jsonl`, one shared-contract event per line |

The eight R1 entity CSVs and `Event-Log.jsonl` are byte-identical to the pinned R1 synthetic files, which `tools/validate.py` checks. See `docs/export-model.md`.
