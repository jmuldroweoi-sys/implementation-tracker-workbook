# Export model

Exports are how workbook data leaves the workbook: to capacity planning (R2), to an AI assistant that drafts status (R6), and to analytics. Every export is generated from a workbook table after recalculation; none is maintained by hand.

## How exports are produced

```bash
python tools/build_workbook.py --exports
```

1. Build the workbook from pinned inputs.
2. Recalculate a copy in headless LibreOffice Calc, so formula columns hold real computed values.
3. Read each Excel Table from the recalculated copy.
4. Write the columns that `config/export-map.yaml` lists for that table, in that order, using R1 field conventions: empty cell for no value, `true` and `false` for flags, semicolons between array items, ISO 8601 text for dates and timestamps.

## Files

| Export | Table | Columns | Consumers |
|---|---|---|---|
| `exports/csv/projects.csv` | `tblProjects` | R1 project CSV contract | R2, analytics |
| `exports/csv/phases.csv` | `tblPhases` | R1 phase CSV contract | R2, analytics |
| `exports/csv/milestones.csv` | `tblMilestones` | R1 milestone CSV contract | analytics |
| `exports/csv/gate-assessments.csv` | `tblGateAssessments` | R1 gate-assessment schema fields | analytics |
| `exports/csv/tasks.csv` | `tblTasks` | R1 task CSV contract | R2, analytics |
| `exports/csv/requests.csv` | `tblRequests` | R1 request CSV contract | R2, analytics |
| `exports/csv/handoffs.csv` | `tblHandoffs` | R1 handoff schema fields | R2, analytics |
| `exports/csv/risks.csv` | `tblRisks` | R1 risk CSV contract (`risk_score` is the formula result) | analytics |
| `exports/csv/issues.csv` | `tblIssues` | R1 issue CSV contract | analytics |
| `exports/csv/readiness.csv` | `tblReadiness` | R1 readiness CSV contract (calculated fields are formula results) | R2, analytics |
| `exports/csv/capacity-inputs.csv` | `tblCapacityInputs` | `schemas/r3/capacity-input.schema.json` | R2 |
| `exports/csv/event-log.csv` | `tblEventLog` | the ten event-contract fields | R2, R6, analytics |
| `exports/jsonl/Event-Log.jsonl` | `tblEventLog` | the ten event-contract fields; payload as a JSON object | R2, R6, analytics |

## Rules

- **Authoritative columns only.** Helper columns (`due_state`, `reference_check`, `risk_band`, `event_evidence`, and every other check) never enter an export.
- **R1 field names and order.** For R1 entities the column list is R1's own CSV contract, so another R1 tool can read the file unchanged.
- **Round trip.** Exporting the bundled synthetic data gives files byte-identical to the pinned R1 synthetic files (eight CSVs and the event JSONL). `tools/validate.py` checks R25 and R26 enforce this, which also proves that the calculated R1 fields equal R1.
- **Capacity Inputs are R3's export format.** Rows carry `capacity_inclusion_method`; R2 must count only `authoritative_workload` rows. The workbook never calculates capacity.

All bundled exports are synthetic data.
