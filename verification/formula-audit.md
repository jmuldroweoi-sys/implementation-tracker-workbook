# Formula audit

How every workbook formula was checked, and what the bundled synthetic data produces. Results are synthetic data, not measured results.

## Method

| Step | Tool | What it proves |
|---|---|---|
| 1. One definition | `tools/workbook_spec.py` | Each calculated column is declared once, with its formula and a Python twin of the same logic |
| 2. Inventory | `FORMULAS.md` (generated) and validator check R11 | Every formula column, KPI row, and capacity check is documented; every formula cell in the workbook equals its declared formula (verifier check W04) |
| 3. Portability scan | verifier check W07, validator check R12 | No `TODAY`, `NOW`, `RAND`, `OFFSET`, `INDIRECT`, `CELL`, `INFO`, `LET`, `LAMBDA`, `XLOOKUP`, `XMATCH`, `FILTER`, `SORT`, `SORTBY`, `UNIQUE`, or `SEQUENCE` |
| 4. Real recalculation | `tools/verify_workbook.py --require-recalc` | Headless LibreOffice Calc 24.2 recalculates the workbook; 0 error values; every one of the formula values equals the reference evaluator (check W13) |
| 5. R1 equality | validator checks R17, R18, R19, R25 | Readiness, risk, and escalation results equal R1's own pinned `r1_rules.py`; exported R1 entities are byte-identical to the pinned R1 files |
| 6. Edge cases | `tests/test_formulas.py` | Each edge case below gives the stated result in the reference evaluator and the same value after LibreOffice recalculation |
| 7. Double counting | `tests/test_capacity.py` | The capacity rules below hold on fixtures |

## Formula inventory counts

| Group | Formula cells in the bundled workbook |
|---|---|
| Reproduce an R1 rule (risk, readiness, escalation, vocabulary, actor and transition checks) | 180 |
| Summarize R1 records (lookups and counts) | 80 |
| R3 checks and views (due states, references, predecessors) | 170 |
| Event reconciliation (`event_evidence` columns and Event Log checks) | 312 |
| Capacity inputs (row formulas and 11 summary checks) | 361 |
| KPI rows | 15 |
| Total | 1,118 |

Formula columns: 71. Every calculated value is documented in `FORMULAS.md`.

## Edge cases tested

| Area | Case | Result |
|---|---|---|
| Tasks | blank due date | `no_due_date` |
| Tasks | completed before due | `completed_on_time` |
| Tasks | completed after due | `completed_late` |
| Tasks | open and before due | `open_not_due` |
| Tasks | open and past due | `overdue` |
| Tasks | blocked (even past due) | `blocked` |
| Tasks | no predecessor | `no_predecessor` |
| Tasks | invalid predecessor | `invalid` |
| Readiness | all six categories present | Project C 91.25 |
| Readiness | missing category | `incomplete_scorecard`, rows flagged `missing_or_extra_category` |
| Readiness | weights valid | the six R1 weights total the R1 `total_weight` (100) |
| Readiness | required evidence missing | `incomplete_required_evidence_flag` TRUE |
| Readiness | score zero | 0 |
| Readiness | full score | 100 |
| Risks | minimum 1 x 1 | 1, `low`, `sev4` |
| Risks | maximum 5 x 5 | 25, `critical`, `sev1` |
| Risks | invalid scale values (6, 0, 2.5, blank) | `invalid_scale_value` |
| Requests | no escalation timer | `no_escalation_timer` |
| Requests | escalation due later | `due_later` |
| Requests | escalation due exactly at `calculation_as_of_at` | `escalation_due` |
| Requests | closed | `closed` |
| Requests | escalation time that disagrees with R1 | `escalation_due_check` = `mismatch` |
| Empty workbook | no projects, tasks, risks, requests, or readiness assessments | every KPI 0, readiness by project blank, 0 error values after recalculation |

## Capacity double-count tests

| Rule | Test |
|---|---|
| One workload component can be authoritative only once | `test_component_can_be_authoritative_only_once`: both duplicate rows flagged, excluded from totals, not export ready |
| Duplicate rows are rejected or flagged | the same test, plus `test_duplicate_rows_are_rejected_by_the_schema_for_requests` (the capacity-input schema rejects an authoritative request row) |
| Informational rows do not add to authoritative totals | `test_informational_rows_do_not_add_to_totals` |
| Excluded rows do not add to totals | `test_excluded_rows_do_not_add_to_totals` |
| Task hours are not counted again because a request or handoff references the task | `test_request_referencing_a_task_does_not_count_it_again` |
| Every task is counted | `test_missing_task_row_is_reported` |
| The workbook agrees with the reference | `test_duplicate_case_recalculates_identically` (LibreOffice) |

## Bundled results

| Value | Result |
|---|---|
| Risk scores `RSK-000001` to `RSK-000006` | 6, 12, 9, 8, 12, 10 (moderate, high, moderate, moderate, high, high), equal to R1 |
| Readiness | `RDS-000001` 16.25, `RDS-000002` 37.5, `RDS-000003` 91.25; all three with incomplete required evidence; equal to R1 |
| Escalation | `REQ-000002` escalation due (2026-09-26T15:00:00Z); `REQ-000003` and `REQ-000008` due later; five with no timer or closed; all consistent with R1 |
| Task due states | 13 completed on time, 6 completed late, 8 open and not due, 2 overdue (`TSK-000012`, `TSK-000013`), 1 blocked (`TSK-000011`) |
| Capacity | 230 planned and 197.5 actual authoritative hours, equal to the Tasks tab; 30 authoritative, 2 informational, 3 excluded rows; 0 duplicates |
| KPI Summary | 3 projects, 3 active, 11 open tasks, 1 blocked, 2 overdue, 4 open risks, 2 open issues, 8 requests, 1 escalation due, 3 scorecards, 3 with incomplete evidence, 38 event rows, 0 failing event rows, 27 changes missing event evidence, 0 reference problems |

The full expected values are in `expected-values.yaml`.
