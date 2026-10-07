# Practical workflow: one week in the tracker

How can one implementation professional use this workbook directly in their job? By running this weekly routine in it. This page is an illustrative example built on synthetic data. Its only subject is **Synthetic Project A** (`PRJ-000001`, customer label "Synthetic Organization A", organization stage `startup`), run by one person, Person A (`PER-000001`), who holds every internal role. Where a step shows an action the data set does not contain, it says so. No real company, customer, or result is represented.

On the evaluation date in the bundled workbook (`calculation_as_of_at` = `2026-10-05T23:59:59Z`), Project A is in its Discover phase (`PHS-000002`), with three completed tasks, three open tasks, one moderate risk, and one request in progress.

## Trigger

The start of the working week. Person A opens the workbook on Monday, in Starter Mode, before the first customer call.

## Inputs

| Input | Where |
|---|---|
| The workbook | `workbook/implementation-tracker-workbook.xlsx` (a personal copy; see `IMPORT-GUIDE.md`) |
| The evaluation time | README tab, `calculation_as_of_at` |
| Last week's progress | Person A's notes and the customer's replies |
| R1 rules | Already inside the workbook: Lookups and Escalation Rules mirror the pinned R1 version |

## Steps

### Step 1. Open workbook

- **Tab used:** README.
- **User action:** Open the personal copy. Read the README tab's pinned R1 commit and the settings table.
- **Formula or rule involved:** None. The file contains no macros and no external links, so it opens without prompts.
- **Authoritative source:** `standard/standard-reference.yaml` (R1 commit `9acd25a`, shared standard 1.0.0).
- **Event implications:** None.
- **Downstream consumer:** None.

### Step 2. Confirm calculation_as_of_at

- **Tab used:** README.
- **User action:** Set `calculation_as_of_at` to the current moment in ISO 8601 UTC, for example `2026-10-05T23:59:59Z` as in the bundled file. Leave `event_reconciliation_from_at` at the start of the period being reconciled.
- **Formula or rule involved:** Every due-state and escalation-state formula reads this named cell. No formula reads the clock.
- **Authoritative source:** `config/workbook-settings.yaml` (a user-configurable parameter).
- **Event implications:** None.
- **Downstream consumer:** Every time-based check in the workbook.

### Step 3. Review Projects

- **Tab used:** Projects.
- **User action:** Confirm Project A's row: status `active`, current phase `PHS-000002`, target launch `2026-12-01`. Read the grey columns.
- **Formula or rule involved:** `current_phase_key` shows `discover`; `reference_check` shows `valid` (the current phase belongs to the project and all three profiles exist); `event_evidence` shows `logged` (`project.created` is `EVT-000001`).
- **Authoritative source:** R1 `schemas/project.schema.json`; project statuses come only from R1.
- **Event implications:** A change of `project_status` would need a `project.status_changed` row.
- **Downstream consumer:** R2 (future workload), analytics.

### Step 4. Update phase

- **Tab used:** Phases and Gates.
- **User action:** Confirm `PHS-000002` (discover) is `active` and nothing moved this week. When the discover gate passes in a later week, Person A will set `exited_at` and status `completed` on `PHS-000002` and add a new design row with `entered_at` (an illustrative example; not in the data set).
- **Formula or rule involved:** `gate_check` confirms `discover_gate` is the R1 gate for this phase; `event_evidence` shows `logged` for the entry (`EVT-000015`). Phase moves follow R1 `lifecycle/lifecycle.yaml`: one phase forward after a pass or pass_with_conditions.
- **Authoritative source:** R1 `lifecycle/lifecycle.yaml` and `lifecycle/gates.yaml`.
- **Event implications:** Each exit and entry needs `phase.exited` and `phase.entered` rows.
- **Downstream consumer:** R2 (phase position drives the kind of work coming), R4 (training timing).

### Step 5. Update tasks

- **Tab used:** Tasks.
- **User action:** Update `TSK-000004` (Map current process steps): still `in_progress`, `actual_hours` 5. Confirm `TSK-000005` and `TSK-000006` are planned. Read `due_state` for each.
- **Formula or rule involved:** `due_state` uses `calculation_as_of_at`: `TSK-000001` to `TSK-000003` are `completed_on_time`; `TSK-000004` to `TSK-000006` are `open_not_due`. `predecessor_reference_valid` is `valid` for every task with predecessors (`TSK-000006` depends on `TSK-000004` and `TSK-000005`).
- **Authoritative source:** R1 `schemas/task.schema.json`; task statuses from R1.
- **Event implications:** `TSK-000002` and `TSK-000003` show `missing:task.status_changed`: they were completed inside the reconciliation window with no event row (handled in step 10).
- **Downstream consumer:** R2 reads `planned_hours` and `actual_hours` through Capacity Inputs.

### Step 6. Add or update risk

- **Tab used:** Risks and Issues.
- **User action:** Review `RSK-000001` (key stakeholders have limited time during discovery). Person A keeps likelihood 3 and impact 2.
- **Formula or rule involved:** `risk_score` = likelihood x impact = 6 on the R1 1 to 5 scale; `risk_band` = `moderate`; `risk_severity` = `sev3`. Typing outside the scale is rejected by the drop-down rule and shown as `invalid_scale_value`.
- **Authoritative source:** R1 `config/risk-rules.yaml` (mirrored in `tblRuleParameters` and `tblRiskBands`).
- **Event implications:** `risk.logged` exists (`EVT-000020`); a later status change would need `risk.status_changed`.
- **Downstream consumer:** Analytics; R6 may summarize open risks in a draft status note.

### Step 7. Process request

- **Tab used:** Requests and Handoffs.
- **User action:** Review `REQ-000001` (confirm which current-state reports are still used), status `in_progress`. When the answer arrives, Person A will move it to `closed` (a legal R1 transition) and set `status_changed_at` (an illustrative example; not in the data set).
- **Formula or rule involved:** `status_check` is `valid`; `escalation_rule_id` is blank because R1 sets no timer for `in_progress`; `escalation_due_state` is `no_escalation_timer`.
- **Authoritative source:** R1 `config/request-state-machine.yaml` and `config/sla-rules.yaml` (mirrored on Escalation Rules).
- **Event implications:** `event_evidence` shows `missing:request.submitted`: the request was submitted on 2026-09-16, inside the window, with no event row.
- **Downstream consumer:** R2 (request workload).

### Step 8. Prepare gate evidence

- **Tab used:** Phases and Gates (with Tasks and Risks and Issues).
- **User action:** Prepare for the discover gate: collect the current-state summary and the requirements list (both required by R1), and the risk entries (optional for a startup profile). Note that `TSK-000004` and `TSK-000006`, both critical, are still open.
- **Formula or rule involved:** The R1 gate checks `critical_tasks_closed` and `critical_milestones_achieved` are not met yet. The workbook shows the state; it never records an outcome.
- **Authoritative source:** R1 `lifecycle/gates.yaml` (`discover_gate`) and the startup profile in `profiles/examples/`.
- **Event implications:** When Person A records the outcome in `tblGateAssessments`, a `gate.assessed` row follows.
- **Downstream consumer:** R4 (gate events signal enablement timing), analytics.

### Step 9. Review readiness

- **Tab used:** Readiness Scorecard.
- **User action:** Glance at `RDS-000001`, Project A's early pre-assessment. No update this week: launch is two months away.
- **Formula or rule involved:** `overall_score` = 16.25 with `incomplete_required_evidence_flag` TRUE. The R1 weights come from `tblReadinessWeights`.
- **Authoritative source:** R1 `config/readiness-weights.yaml`.
- **Event implications:** `readiness.scored` exists (`EVT-000032`).
- **Downstream consumer:** R2 (reporting); the human launch reviewer later. The score never decides go or no-go.

### Step 10. Append or reconcile material events

- **Tab used:** Event Log (with each record tab's `event_evidence` column).
- **User action:** Append rows for the three gaps in Project A, following `config/event-mappings.yaml`: `task.status_changed` for `TSK-000002` and `TSK-000003`, and `request.submitted` for `REQ-000001`. For example (an illustrative example; not in the data set): `event_type` `request.submitted`, `actor_id` `PER-000001`, `actor_type` `human`, `subject_type` `request`, `subject_id` `REQ-000001`, `payload` `{"project_id": "PRJ-000001", "request_type": "information"}`, `source_repo` `implementation-operating-system`, `schema_version` `1.0.0`.
- **Formula or rule involved:** The Event Log check columns confirm each new row's type, actor, subject, and payload shape; the record's `event_evidence` turns to `logged`.
- **Authoritative source:** R1 `standard/event-catalog.yaml` and `standard/schemas/event.schema.json`.
- **Event implications:** This step is the event trail. Nothing is appended automatically.
- **Downstream consumer:** R2, R6, and analytics read the Event Log export.

### Step 11. Review KPI Summary

- **Tab used:** KPI Summary.
- **User action:** Read the counts across all projects and the "Projects by Current Phase" chart. For Project A, nothing is overdue and no escalation is due.
- **Formula or rule involved:** Deterministic counts only, for example `overdue_task_count`, `open_risk_count`, `escalation_due_request_count`, and `reference_problem_count` (0). No forecasts, utilization, or performance measures.
- **Authoritative source:** The workbook's R1 records; each KPI's definition is in `FORMULAS.md`.
- **Event implications:** None.
- **Downstream consumer:** Person A's weekly status.

### Step 12. Export Capacity Inputs

- **Tab used:** Capacity Inputs.
- **User action:** Confirm Project A's six task rows (`CPI-000001` to `CPI-000006`) are `authoritative_workload` and `export_ready_flag` is TRUE, then export (monthly in Starter Mode, optional at the startup stage).
- **Formula or rule involved:** Hours are looked up from the tasks (26 planned hours and 16.5 actual hours for Project A); `tblCapacitySummary` shows `hours_reconciliation` `reconciled` and 0 duplicates. No capacity math happens here.
- **Authoritative source:** `schemas/r3/capacity-input.schema.json`; hours from R1 task records.
- **Event implications:** None.
- **Downstream consumer:** R2 capacity planning.

### Step 13. Prepare weekly status

- **Tab used:** Projects, Tasks, Risks and Issues, Requests and Handoffs, KPI Summary.
- **User action:** Write three lines for the customer sponsor of Synthetic Organization A: discovery on track (`TSK-000004` in progress, due 2026-10-07), one moderate risk on stakeholder time, one open question on current-state reports.
- **Formula or rule involved:** None new; the status cites values the workbook already shows.
- **Authoritative source:** The workbook records.
- **Event implications:** None.
- **Downstream consumer:** The customer sponsor; later, R6 may draft this note for Person A to review and approve.

### Step 14. Verify workbook

- **Tab used:** All, plus the command line.
- **User action:** Scan the grey check columns for anything other than `valid`, then run the checks.
- **Formula or rule involved:** `tools/validate.py` (38 checks) and `tools/verify_workbook.py` (15 checks, with LibreOffice recalculation).
- **Authoritative source:** The pinned R1 version and `verification/expected-values.yaml`.
- **Event implications:** Missing event evidence is reported, not hidden.
- **Downstream consumer:** Anyone who will read the exports.

## Deterministic rules

| Rule | R1 source | Where in the workbook |
|---|---|---|
| Risk score = likelihood x impact; band and severity | `config/risk-rules.yaml` | `tblRisks[risk_score]`, `[risk_band]`, `[risk_severity]` |
| Readiness: rate, category score, overall score, incomplete-evidence flag | `config/readiness-weights.yaml` | `tblReadiness` calculated columns |
| Request statuses and legal transitions | `config/request-state-machine.yaml` | `tblRequests[status_check]`, `tblEventLog[request_transition_check]` |
| Escalation time = time entered status + target duration | `config/sla-rules.yaml` | `tblRequests[escalation_rule_id]`, `[escalation_due_check]` |
| Gate belongs to its phase; outcome is pass, pass_with_conditions, or hold | `lifecycle/gates.yaml`, `standard/lifecycle-terms.yaml` | `tblPhases[gate_check]`, `tblGateAssessments[outcome_check]` |
| Due state as of the evaluation time | R3 view | `tblTasks[due_state]` |

## Outputs

- Updated records on the Projects, Tasks, Risks and Issues, and Requests and Handoffs tabs, with R1 IDs unchanged.
- New Event Log rows for material changes.
- A capacity-input export (`exports/csv/capacity-inputs.csv`) when due.
- A three-line weekly status for the sponsor.

## Events

Only registered R1 core events: in this week, `task.status_changed` and `request.submitted`; across Project A's life, also `project.created`, `phase.entered`, `phase.exited`, `gate.assessed`, `milestone.achieved`, `risk.logged`, `handoff.completed`, and `readiness.scored`.

## Human decisions

| Decision | Who |
|---|---|
| Task status, hours, and dates | Person A (owner roles) |
| Risk likelihood and impact | Person A (risk owner role) |
| Request moves | The request's owner role, along legal R1 transitions |
| Gate outcome | Person A, recorded by name in `tblGateAssessments` |
| Launch decision | A named person at the launch gate; the readiness score only informs it |
| What goes in the weekly status | Person A |

No formula and no AI makes any of these decisions.

## Downstream integrations

- **R2 capacity:** reads `exports/csv/capacity-inputs.csv` and counts only `authoritative_workload` rows.
- **R1:** the workbook's R1 entity exports use R1's own CSV contracts and can be read by R1 tooling.
- **R6 AI assistance:** may read exports and draft status notes; a named person approves anything that changes.
- **Analytics:** may read the Event Log JSONL and CSV exports.

## Verification

Person A checks that every `reference_check` is `valid`, that the KPI rows `reference_problem_count` and `event_log_problem_count` are 0, and that `hours_reconciliation` reads `reconciled`. Before sharing exports, run `python tools/validate.py` and `python tools/verify_workbook.py --require-recalc`.

## Solo use

Person A holds every role, works in Starter Mode, records gates as lightweight self-assessments, and keeps the weekly routine above. Capacity exports and full reconciliation are optional at the startup stage.

## Early-scale use

A small team shares one workbook. Each person owns roles; event rows for material changes and weekly validation become required (`config/stage-requirements.yaml`), and requests escalate to the delivery leadership role by R1 rule.

## Structured-growth use

Specialists hold separate roles, gate evidence is complete, the launch gate is recorded by a named approver other than the project owner, full event reconciliation is required, and capacity inputs are exported for planning.

## Mature use

Several teams keep workbooks (or move to a database-backed R1 implementation) on the same model. Monthly capacity exports are required, Event Log exports feed portfolio reporting, and changes to the pinned R1 version are rolled out by re-syncing and revalidating.
