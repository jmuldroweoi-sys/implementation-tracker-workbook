# Architecture

The workbook is R1's spreadsheet reference implementation. R1 defines the operating model; the workbook applies it. This page shows how the parts fit and where each decision lives.

## Layers

```text
R1 implementation-operating-system (authority)
  standard/ lifecycle/ schemas/ config/ profiles/ data/synthetic/ tools/r1_rules.py
        |
        |  tools/sync_r1_contracts.py --r1-commit FULL_SHA   (explicit pin, never "latest")
        v
schemas/r1/ and data/synthetic/r1/   byte-identical copies + SHA-256 manifests
        |
        |  tools/workbook_spec.py      one definition of every table, column, and formula
        |  tools/build_workbook.py     reproducible build (fixed timestamps)
        v
workbook/implementation-tracker-workbook.xlsx   12 tabs, 24 tables, 1,118 formulas, no macros
        |
        |  headless recalculation, then table export
        v
exports/csv/*.csv  exports/jsonl/Event-Log.jsonl   (R1 entity exports byte-identical to R1)
```

Checking runs alongside:

```text
tools/reference_model.py   Python twin of every formula; R1 values from pinned r1_rules.py
tools/verify_workbook.py   workbook structure + LibreOffice recalculation vs reference
tools/validate.py          38 repository checks (pins, hashes, parity, exports, docs, safety)
```

## Authority

| Concern | Owner | Where the workbook gets it |
|---|---|---|
| Lifecycle phases, phase statuses, gate outcomes | R1 | `schemas/r1/standard/lifecycle-terms.yaml` into `lst_phase_key`, `lst_phase_status`, `lst_gate_outcome` |
| Gates per phase | R1 | `schemas/r1/lifecycle/gates.yaml` into `lst_gate_id` |
| Project, task, milestone, handoff, risk, issue statuses | R1 | the pinned R1 record schemas |
| Request statuses and transitions | R1 | `schemas/r1/config/request-state-machine.yaml` |
| Severities | R1 | `schemas/r1/standard/severity-scale.yaml` |
| Risk scale, formula, bands | R1 | `schemas/r1/config/risk-rules.yaml` into `tblRuleParameters` and `tblRiskBands` |
| Readiness categories and weights | R1 | `schemas/r1/standard/readiness-categories.yaml` and `schemas/r1/config/readiness-weights.yaml` into `tblReadinessWeights` |
| SLA and lead-time parameters | R1 | `schemas/r1/config/sla-rules.yaml` and `lead-time-rules.yaml` into `tblEscalationRules` |
| Event types and payload fields | R1 | `schemas/r1/standard/event-catalog.yaml` |
| Workbook layout, formulas, checks, exports, metadata, Capacity Inputs format | R3 | this repository |
| Gate outcomes, launch decisions, handoff acceptance | A named person | entered in `tblGateAssessments` and `tblHandoffs`; never calculated |

The workbook contains no lifecycle file, no second readiness-category or weight definition, no second risk-rule source, no independent request state machine, and no alternate event catalog. `tools/validate.py` check R36 enforces this.

## One definition, three uses

`tools/workbook_spec.py` declares each table and column once. A calculated column carries two forms of the same logic: the spreadsheet formula and a Python twin. The builder writes the formula; the reference evaluator runs the twin; the verifier compares the recalculated workbook with the twin's results for every formula cell. The formula inventory in `FORMULAS.md` and the data dictionary are generated from the same declarations.

## Reproducibility

- The builder reads only pinned inputs and committed configuration.
- Document timestamps are the pinned R1 synchronization time, and package entries carry a fixed date, so a rebuild is byte-identical. The verifier rebuilds and compares.
- Formulas never read the clock. `calculation_as_of_at` is an explicit setting.

## Scaling

One workbook serves every organization stage. `config/stage-requirements.yaml` marks fields and controls required, recommended, or optional per stage, and Starter Mode or Full Mode changes how much a person updates each week. Neither changes the tables, the IDs, the event contract, the readiness categories, or who decides a gate.

## What later software could do that the workbook does not

A database-backed implementation of R1 could append events automatically on every change, enforce transitions at write time, and keep an immutable audit trail. The workbook deliberately does none of these; it makes the gaps visible instead (see `event-capture-model.md`).
