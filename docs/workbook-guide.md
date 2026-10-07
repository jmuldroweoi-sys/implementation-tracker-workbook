# Workbook guide

How to work in `workbook/implementation-tracker-workbook.xlsx`, tab by tab, in Starter Mode and Full Mode. For the one-hour weekly routine, see [starter-mode.md](starter-mode.md). Every bundled row is synthetic data and an illustrative example.

## Reading the workbook

| You see | It means |
|---|---|
| Dark blue header, white cells | A record field. Edit it. Its name is the R1 field name. |
| Grey header, grey cells | A formula. Do not type over it. `FORMULAS.md` documents it. |
| Green header | A read-only mirror of R1 configuration or vocabulary. |
| Yellow cell (README) | A setting you may change. |
| Light red fill | A failed check or an overdue task. |
| Amber fill | A blocked task, an escalation that is due, missing event evidence, or incomplete readiness evidence. |

## Settings (README tab)

| Setting | Use |
|---|---|
| `calculation_as_of_at` | The time every due state and escalation state is evaluated at. ISO 8601 UTC with `Z`. A user-configurable parameter. |
| `event_reconciliation_from_at` | Changes at or after this time must have an Event Log row. A user-configurable parameter. |
| `selected_org_stage` | Your organization stage. See `config/stage-requirements.yaml`. |
| `operating_mode` | `starter` or `full`. |

## Tabs

1. **README.** The guide and the settings table. Protected (no password) except the yellow value cells.
2. **Lookups.** Every drop-down list (`tblLookupEntries`, 29 named lists `lst_*`) and the R1 readiness weights, risk bands, and rule parameters. Protected and generated from the pin.
3. **Projects.** `tblProjects`: one row per project with R1 fields. Checks: `current_phase_key`, `reference_check`, `event_evidence`.
4. **Phases and Gates.** `tblPhases` (one row per phase instance, including rework instances), `tblMilestones`, and `tblGateAssessments`. A person records each gate outcome; the checks confirm the outcome is a standard value, the assessor is a named person, and the gate belongs to the phase.
5. **Tasks.** `tblTasks` with hours, dates, and predecessors. Checks: `due_state`, `predecessor_reference_valid`, `reference_check`, `event_evidence`.
6. **Requests and Handoffs.** `tblRequests` uses the nine R1 request statuses. `escalation_rule_id`, `escalation_due_check`, and `escalation_due_state` show the R1 timer for the current status. `tblHandoffs` records who accepted each handoff.
7. **Escalation Rules.** `tblEscalationRules` mirrors the 8 R1 SLA rules and 4 lead-time rules. "Source of truth: R1 configuration." Editing it would not change R1, so the tab is protected.
8. **Risks and Issues.** `tblRisks` calculates `risk_score`, `risk_band`, and `risk_severity`; `tblIssues` checks severity.
9. **Readiness Scorecard.** `tblReadiness` (six rows per scorecard) and `tblReadinessSummary` (one row per scorecard). Enter criteria counts and the required-evidence flag; the rest is calculated. The score informs human review and decides nothing.
10. **Capacity Inputs.** `tblCapacityInputs` classifies workload rows; `tblCapacitySummary` proves nothing is double counted.
11. **Event Log.** `tblEventLog`, ten contract columns plus six check columns.
12. **KPI Summary.** Fifteen operational counts, projects by phase (with a chart), requests by status, and readiness by project.

## Starter Mode

Starter Mode is for one person with a few projects. You still have the whole model; you simply touch fewer tabs each week: Projects, Tasks, Risks and Issues, Requests and Handoffs, Readiness when a launch is near, Event Log only for material changes, and KPI Summary. Gate outcomes are still recorded in `tblGateAssessments` when a gate happens. See [starter-mode.md](starter-mode.md).

## Full Mode

Full Mode uses all 12 tabs with more structure:

- **Complete gate evidence.** For every gate, list the evidence types reviewed (`evidence_types_provided`) and the records reviewed (`evidence_refs`), and track each condition (`condition_refs`).
- **Capacity exports.** Each month, review `tblCapacityInputs` and `tblCapacitySummary` and export `exports/csv/capacity-inputs.csv` for capacity planning.
- **Full event reconciliation.** Every `event_evidence` cell inside the window reads `logged` and every Event Log check passes.
- **Structured governance.** A named approver other than the project owner records the launch gate at structured-growth and mature stages (R1 `lifecycle/gates.yaml` stage behavior).

Same workbook. Same IDs. Same R1 authority.

## What the workbook never does

It never decides a gate or a launch, changes a status by itself, appends an event, reads the clock, calculates capacity or staffing, or uses AI.
