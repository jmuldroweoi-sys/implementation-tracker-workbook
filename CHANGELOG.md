# Changelog

This file tracks the workbook (R3) version. The pinned R1 commit and shared-standard version are stated in each entry and in `standard/standard-reference.yaml`.

## [0.1.0] 2026-10-07

Pinned R1 commit `9acd25a4673facf2b3cca2467142987548949ce3` (R1 repository version 0.1.0). Shared standard 1.0.0.

### Added

- `workbook/implementation-tracker-workbook.xlsx`: macro-free, 12 visible tabs, 24 Excel Tables, 1,118 formula cells, no hidden sheets, no external links, no volatile functions.
- Version-pinned R1 contracts (`schemas/r1/`, 33 files) and R1 synthetic inputs (`data/synthetic/r1/`, 9 files), each with a SHA-256 manifest, and `tools/sync_r1_contracts.py` to change the pin only from an explicit R1 commit.
- R3 schemas: workbook metadata (`WBK`), lookup entry (`LKP`), capacity input (`CPI`).
- Configuration: workbook settings, validation lists (each citing its R1 source), stage requirements, event mappings, export map.
- R3 synthetic data: 35 capacity-input rows.
- Exports generated from the recalculated workbook: 12 CSV files and `exports/jsonl/Event-Log.jsonl`. The eight R1 entity exports and the event JSONL are byte-identical to the pinned R1 files.
- Tools: reproducible builder, workbook verifier with headless LibreOffice recalculation, reference evaluator, repository validator (38 checks).
- Documentation: README, formulas, import guide, architecture, workbook guide, data dictionary, Starter Mode, event-capture model, export model, practical workflow, portfolio integration.
- Tests and verification records.

### Fixed

- Reproducible build depended on whether the optional lxml package was installed: openpyxl writes XML differently with lxml, so CI (without lxml) rebuilt different bytes. The builder now always uses openpyxl's standard XML writer and refuses to build if lxml serialization is active. Regression test: `test_build_does_not_depend_on_optional_lxml`.

### Changed (publication-readiness review)

- Readability: columns are wide enough that no header name splits mid-word and task, risk, and issue text is readable; the KPI chart counts whole projects (axis steps of 1). No formula or value changed.
- README: two screenshots rendered from the bundled synthetic workbook (`docs/images/`, produced by `tools/render_screenshots.py`); the R1/R3 relationship on the first screen; a "Where to find things" map; an author line; the Excel limitation stated plainly (Excel spot-check not performed; LibreOffice 24.2 verified).
- `tools/validate.py` R30 stores its vendor and product list as SHA-256 hashes and matches whole words case-sensitively; tests cover the matcher.

### Not yet included

- R4-owned tabs (curriculum, deliverables, training roster, proficiency) and scenario-pack tabs (cutover runbook, command center), planned for version 0.2 after their owning repositories exist.
