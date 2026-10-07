# Contributing

This workbook implements R1 (`implementation-operating-system`). It never redefines what R1 owns. Every change is reviewed by a human before it merges.

## What may change here

- Workbook structure, styling, check columns, and R3-only views.
- Formulas that implement an R1 rule, provided they still reproduce R1 exactly.
- Imports, exports, and the Capacity Inputs format.
- R3 schemas (`schemas/r3/`) and R3 configuration (`config/`).

## What may never change here

- Anything under `schemas/r1/` or `data/synthetic/r1/`. These are byte-identical copies of a pinned R1 commit. Change R1 first, then run `tools/sync_r1_contracts.py --r1-repo PATH --r1-commit FULL_SHA`, rebuild, and revalidate.
- Status lists, transitions, severities, readiness categories or weights, risk scales or bands, SLA or lead-time parameters, or event definitions. They come from R1.
- Gate outcomes or launch decisions. A named person records them; no formula decides them.

## Change process

1. Edit `tools/workbook_spec.py` (tables, columns, formulas, and each formula's Python twin), never the `.xlsx` file.
2. Rebuild: `python tools/build_workbook.py --exports` and `python tools/build_workbook.py --docs`.
3. Regenerate expected values if results changed (see `verification/expected-values.yaml`), and explain why in the change.
4. Run every check: `python tools/validate.py`, `python tools/verify_workbook.py --require-recalc`, `python -m unittest discover -s tests -v`.
5. Record the change in `CHANGELOG.md`.

## Public-safety requirements

- Write everything freshly. Never copy wording, structure, or screenshots from any organization's documents, trackers, or systems.
- Never include real names of people, customers, employers, vendors, products, or internal tools, and never include real metrics or real exports.
- Run the validator with the private blocklist (`--blocklist FILE`, kept outside this repository) before any change intended for publication.

## Labels

Synthetic records are labeled synthetic data; examples are labeled illustrative example; adjustable values are labeled user-configurable parameter; design numbers are labeled proposed design value, not a measured result. Use the exact wording; the validator rejects near-variants.
