# Changelog

This file tracks the workbook (R3) version. The pinned R1 commit and shared-standard version are stated in each entry and in `standard/standard-reference.yaml`.

## [0.1.0] Unreleased (pre-release, not tagged)

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

### Not yet included

- R4-owned tabs (curriculum, deliverables, training roster, proficiency) and scenario-pack tabs (cutover runbook, command center), planned for version 0.2 after their owning repositories exist. No release or tag exists yet.
