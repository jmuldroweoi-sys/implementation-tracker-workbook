# Formulas

Every calculated cell in `workbook/implementation-tracker-workbook.xlsx`, what it does, and where its rule comes from. The workbook has no silent spreadsheet authority: each formula is classified as one of the following.

| Classification | Meaning |
|---|---|
| `reproduces_r1_rule` | Implements a deterministic R1 rule or vocabulary check. The rule and its parameters are read from the pinned R1 copies under `schemas/r1/`. |
| `summarizes_r1_records` | Counts, looks up, or copies R1 record values without adding logic. |
| `r3_workbook_validation` | An R3-only view or check (due states, reference checks, event reconciliation, capacity-input controls). It never changes an R1 record or decides anything. |

## Conventions

- **No clock.** No formula uses `TODAY()` or `NOW()`. Time-based results compare against the named cell `calculation_as_of_at` (README tab), an explicit ISO 8601 UTC value and a user-configurable parameter.
- **ISO text.** Dates and timestamps are stored as ISO 8601 text, so exports reproduce R1 values exactly. Comparisons are text comparisons of ISO values, which order correctly. A date compared with a timestamp counts as the end of that day where noted.
- **Portable functions only.** `IF`, `IFERROR`, `INDEX`, `MATCH`, `COUNTIF`, `COUNTIFS`, `SUMIFS`, `SUMPRODUCT`, `AND`, `OR`, `NOT`, `ROUND`, `LEFT`, `MID`, `LEN`, `SUBSTITUTE`, `SEARCH`, `FIND`, `TRIM`, `RIGHT`, `ISNUMBER`, `INT`, `ABS`, `ROWS`, `SUM`, `DATEVALUE`, `TIMEVALUE`. No `LET`, `LAMBDA`, `XLOOKUP`, dynamic arrays, `OFFSET`, or `INDIRECT`.
- **Structured references.** Formulas use Excel Table references, with this-row references in their stored form `tblName[[#This Row],[column]]`.
- **Blank rows are quiet.** Every per-row formula returns an empty value when the row's own ID is blank, so empty tables never show `#DIV/0!` or `#N/A`. Divisions are guarded, and lookups are wrapped in `IFERROR` with a named fallback such as `phase_not_found`.
- **No hardcoded R1 numbers.** Weights, bands, scale bounds, and durations come from mirror tables on the Lookups and Escalation Rules tabs, which the builder fills from the pinned R1 configuration.

## How the formulas are verified

1. `tools/workbook_spec.py` declares every formula once, next to a Python twin that computes the value the formula must produce.
2. `tools/reference_model.py` runs those twins on the pinned inputs. Its R1 values come from R1's own pinned `tools/r1_rules.py`.
3. `tools/verify_workbook.py` recalculates the workbook with headless LibreOffice Calc and compares every formula cell with the reference value. It also checks that the R1 entity exports are byte-identical to the pinned R1 files, which proves the calculated R1 fields (risk score, readiness weight, achieved rate, category score, overall score, incomplete-evidence flag) equal R1.

## Capacity inputs: no double counting

The Capacity Inputs tab prepares workload hours for future capacity planning (R2). It does not calculate capacity, utilization, staffing need, hiring timing, or a capacity gap.

| Rule | How the workbook enforces it |
|---|---|
| A workload component is authoritative at most once | `duplicate_authoritative_flag` is TRUE on every row that claims an already-authoritative component; such rows get 0 in the authoritative totals and `export_ready_flag` FALSE |
| A task's own effort is the authoritative workload | Task rows (`source_entity_type` task) are `authoritative_workload`; the schema forbids request and handoff rows from being authoritative |
| Work referenced by a request or handoff is not counted again | Those rows point at the task they repeat (`workload_component_id`) and are `excluded_to_prevent_double_count` |
| Summaries already represented by tasks are not added again | Phase summary rows are `informational_only`; their hours equal the sum of the phase's tasks but count 0 toward the totals |
| Totals reconcile | `hours_reconciliation` is `reconciled` only when the authoritative planned and actual totals equal the Tasks tab totals |
| Every task is covered | `tasks_without_authoritative_row` must be 0 |

The tests in `tests/test_capacity.py` prove each rule on fixtures (see `verification/formula-audit.md`).

## Event reconciliation

A macro-free workbook cannot append events by itself. The `event_evidence` columns compare each material change inside the reconciliation window (from `event_reconciliation_from_at`) with the Event Log and show `logged`, `before_window`, `not_required_or_before_window`, or `missing:<event type>`. The Event Log's own check columns verify each row's event type, source repository, actor, subject, payload shape, and request transition. See `docs/event-capture-model.md`.

## Formula inventory

The inventory below is generated from the workbook specification, so it cannot fall out of step with the workbook. For each calculated field it gives the tab, table, field, authority, purpose, R1 source, input fields, edge cases, expected result on the bundled synthetic data, portability notes, and the exact formula. Expected results are synthetic data, not measured results.

<!-- GENERATED FORMULA INVENTORY BELOW -->

<!-- Generated by tools/build_workbook.py --docs from tools/workbook_spec.py. Do not edit by hand. -->

### Projects / `tblProjects`

#### `tblProjects[current_phase_key]`

| Item | Value |
|---|---|
| Workbook tab | Projects |
| Table | `tblProjects` |
| Field | `current_phase_key` (R3 helper, not exported) |
| Authority | `summarizes_r1_records` |
| Purpose | Shows the lifecycle phase key of the project's current phase instance. |
| R1 source rule or config | None: R3 view over R1 records |
| Input fields | `project_id`, `lifecycle_phase_key`, `current_phase_id`, `phase_id` |
| Edge cases | phase_not_found when current_phase_id has no phase row. |
| Expected synthetic result | discover 1, build 1, launch 1 |
| Portability | Functions: IF, IFERROR, INDEX, MATCH (all in the portable set). Uses Excel Table structured references; recalculation verified in LibreOffice Calc 24.2, not yet in Excel itself. |

```text
=IF(tblProjects[[#This Row],[project_id]]="","",IFERROR(INDEX(tblPhases[lifecycle_phase_key],MATCH(tblProjects[[#This Row],[current_phase_id]],tblPhases[phase_id],0))&"","phase_not_found"))
```

#### `tblProjects[reference_check]`

| Item | Value |
|---|---|
| Workbook tab | Projects |
| Table | `tblProjects` |
| Field | `reference_check` (R3 helper, not exported) |
| Authority | `r3_workbook_validation` |
| Purpose | Checks the current phase belongs to this project and the three profile IDs exist. |
| R1 source rule or config | None: R3 view over R1 records |
| Input fields | `project_id`, `phase_id`, `current_phase_id`, `lookup_type`, `key`, `complexity_profile_id`, `service_profile_id`, `segment_profile_id` |
| Edge cases | orphan_current_phase or orphan_profile. |
| Expected synthetic result | valid 3 |
| Portability | Functions: COUNTIFS, IF (all in the portable set). Uses Excel Table structured references; recalculation verified in LibreOffice Calc 24.2, not yet in Excel itself. |

```text
=IF(tblProjects[[#This Row],[project_id]]="","",IF(COUNTIFS(tblPhases[phase_id],tblProjects[[#This Row],[current_phase_id]],tblPhases[project_id],tblProjects[[#This Row],[project_id]])=0,"orphan_current_phase",IF(COUNTIFS(tblLookupEntries[lookup_type],"profile_id",tblLookupEntries[key],tblProjects[[#This Row],[complexity_profile_id]])+COUNTIFS(tblLookupEntries[lookup_type],"profile_id",tblLookupEntries[key],tblProjects[[#This Row],[service_profile_id]])+COUNTIFS(tblLookupEntries[lookup_type],"profile_id",tblLookupEntries[key],tblProjects[[#This Row],[segment_profile_id]])<3,"orphan_profile","valid")))
```

#### `tblProjects[event_evidence]`

| Item | Value |
|---|---|
| Workbook tab | Projects |
| Table | `tblProjects` |
| Field | `event_evidence` (R3 helper, not exported) |
| Authority | `r3_workbook_validation` |
| Purpose | Reconciles project creation against the Event Log. |
| R1 source rule or config | None: R3 view over R1 records |
| Input fields | `project_id`, `created_at`, `subject_id`, `event_type`, `event_reconciliation_from_at` |
| Edge cases | before_window when created before event_reconciliation_from_at. |
| Expected synthetic result | logged 1, before_window 2 |
| Portability | Functions: AND, COUNTIFS, IF, OR (all in the portable set). Uses Excel Table structured references; recalculation verified in LibreOffice Calc 24.2, not yet in Excel itself. |

```text
=IF(tblProjects[[#This Row],[project_id]]="","",IF(AND(TRUE,tblProjects[[#This Row],[created_at]]>=event_reconciliation_from_at,COUNTIFS(tblEventLog[subject_id],tblProjects[[#This Row],[project_id]],tblEventLog[event_type],"project.created")=0),"missing:project.created",IF(OR(AND(TRUE,tblProjects[[#This Row],[created_at]]>=event_reconciliation_from_at)),"logged","before_window")))
```

### Phases and Gates / `tblPhases`

#### `tblPhases[reference_check]`

| Item | Value |
|---|---|
| Workbook tab | Phases and Gates |
| Table | `tblPhases` |
| Field | `reference_check` (R3 helper, not exported) |
| Authority | `r3_workbook_validation` |
| Purpose | Checks that the referenced project exist in this workbook. |
| R1 source rule or config | None: R3 view over R1 records |
| Input fields | `phase_id`, `project_id` |
| Edge cases | Returns orphan_project or orphan_phase when a reference does not resolve. |
| Expected synthetic result | valid 15 |
| Portability | Functions: COUNTIF, IF (all in the portable set). Uses Excel Table structured references; recalculation verified in LibreOffice Calc 24.2, not yet in Excel itself. |

```text
=IF(tblPhases[[#This Row],[phase_id]]="","",IF(COUNTIF(tblProjects[project_id],tblPhases[[#This Row],[project_id]])=0,"orphan_project","valid"))
```

#### `tblPhases[gate_check]`

| Item | Value |
|---|---|
| Workbook tab | Phases and Gates |
| Table | `tblPhases` |
| Field | `gate_check` (R3 helper, not exported) |
| Authority | `reproduces_r1_rule` |
| Purpose | Checks gate_id is the R1 gate for this phase (lifecycle/gates.yaml); Review has none. |
| R1 source rule or config | lifecycle/gates.yaml (gates.phase_id) |
| Input fields | `phase_id`, `lookup_type`, `display_value`, `lifecycle_phase_key`, `gate_id`, `key` |
| Edge cases | gate_mismatch or unexpected_gate. |
| Expected synthetic result | valid 15 |
| Portability | Functions: COUNTIFS, IF (all in the portable set). Uses Excel Table structured references; recalculation verified in LibreOffice Calc 24.2, not yet in Excel itself. |

```text
=IF(tblPhases[[#This Row],[phase_id]]="","",IF(COUNTIFS(tblLookupEntries[lookup_type],"gate_id",tblLookupEntries[display_value],tblPhases[[#This Row],[lifecycle_phase_key]])=0,IF(tblPhases[[#This Row],[gate_id]]="","valid","unexpected_gate"),IF(COUNTIFS(tblLookupEntries[lookup_type],"gate_id",tblLookupEntries[key],tblPhases[[#This Row],[gate_id]],tblLookupEntries[display_value],tblPhases[[#This Row],[lifecycle_phase_key]])>0,"valid","gate_mismatch")))
```

#### `tblPhases[event_evidence]`

| Item | Value |
|---|---|
| Workbook tab | Phases and Gates |
| Table | `tblPhases` |
| Field | `event_evidence` (R3 helper, not exported) |
| Authority | `r3_workbook_validation` |
| Purpose | Reconciles phase entry and exit against the Event Log. |
| R1 source rule or config | None: R3 view over R1 records |
| Input fields | `phase_id`, `entered_at`, `subject_id`, `event_type`, `exited_at`, `event_reconciliation_from_at` |
| Edge cases | Checks entry first, then exit. |
| Expected synthetic result | logged 7, before_window 8 |
| Portability | Functions: AND, COUNTIFS, IF, OR (all in the portable set). Uses Excel Table structured references; recalculation verified in LibreOffice Calc 24.2, not yet in Excel itself. |

```text
=IF(tblPhases[[#This Row],[phase_id]]="","",IF(AND(tblPhases[[#This Row],[entered_at]]<>"",tblPhases[[#This Row],[entered_at]]>=event_reconciliation_from_at,COUNTIFS(tblEventLog[subject_id],tblPhases[[#This Row],[phase_id]],tblEventLog[event_type],"phase.entered")=0),"missing:phase.entered",IF(AND(tblPhases[[#This Row],[exited_at]]<>"",tblPhases[[#This Row],[exited_at]]>=event_reconciliation_from_at,COUNTIFS(tblEventLog[subject_id],tblPhases[[#This Row],[phase_id]],tblEventLog[event_type],"phase.exited")=0),"missing:phase.exited",IF(OR(AND(tblPhases[[#This Row],[entered_at]]<>"",tblPhases[[#This Row],[entered_at]]>=event_reconciliation_from_at),AND(tblPhases[[#This Row],[exited_at]]<>"",tblPhases[[#This Row],[exited_at]]>=event_reconciliation_from_at)),"logged","before_window"))))
```

### Phases and Gates / `tblMilestones`

#### `tblMilestones[reference_check]`

| Item | Value |
|---|---|
| Workbook tab | Phases and Gates |
| Table | `tblMilestones` |
| Field | `reference_check` (R3 helper, not exported) |
| Authority | `r3_workbook_validation` |
| Purpose | Checks that the referenced project and phase (same project) exist in this workbook. |
| R1 source rule or config | None: R3 view over R1 records |
| Input fields | `milestone_id`, `project_id`, `phase_id` |
| Edge cases | Returns orphan_project or orphan_phase when a reference does not resolve. |
| Expected synthetic result | valid 12 |
| Portability | Functions: COUNTIF, COUNTIFS, IF (all in the portable set). Uses Excel Table structured references; recalculation verified in LibreOffice Calc 24.2, not yet in Excel itself. |

```text
=IF(tblMilestones[[#This Row],[milestone_id]]="","",IF(COUNTIF(tblProjects[project_id],tblMilestones[[#This Row],[project_id]])=0,"orphan_project",IF(COUNTIFS(tblPhases[phase_id],tblMilestones[[#This Row],[phase_id]],tblPhases[project_id],tblMilestones[[#This Row],[project_id]])=0,"orphan_phase","valid")))
```

#### `tblMilestones[event_evidence]`

| Item | Value |
|---|---|
| Workbook tab | Phases and Gates |
| Table | `tblMilestones` |
| Field | `event_evidence` (R3 helper, not exported) |
| Authority | `r3_workbook_validation` |
| Purpose | Reconciles achieved and missed milestones against the Event Log. |
| R1 source rule or config | None: R3 view over R1 records |
| Input fields | `milestone_id`, `status`, `completed_date`, `subject_id`, `event_type`, `target_date`, `event_reconciliation_from_at` |
| Edge cases | A date counts as the end of that day when compared with the window timestamp. |
| Expected synthetic result | logged 3, not_required_or_before_window 7, missing:milestone.achieved 2 |
| Portability | Functions: AND, COUNTIFS, IF, OR (all in the portable set). Uses Excel Table structured references; recalculation verified in LibreOffice Calc 24.2, not yet in Excel itself. |

```text
=IF(tblMilestones[[#This Row],[milestone_id]]="","",IF(AND(tblMilestones[[#This Row],[status]]="achieved",tblMilestones[[#This Row],[completed_date]]&"T23:59:59Z">=event_reconciliation_from_at,COUNTIFS(tblEventLog[subject_id],tblMilestones[[#This Row],[milestone_id]],tblEventLog[event_type],"milestone.achieved")=0),"missing:milestone.achieved",IF(AND(tblMilestones[[#This Row],[status]]="missed",tblMilestones[[#This Row],[target_date]]&"T23:59:59Z">=event_reconciliation_from_at,COUNTIFS(tblEventLog[subject_id],tblMilestones[[#This Row],[milestone_id]],tblEventLog[event_type],"milestone.missed")=0),"missing:milestone.missed",IF(OR(AND(tblMilestones[[#This Row],[status]]="achieved",tblMilestones[[#This Row],[completed_date]]&"T23:59:59Z">=event_reconciliation_from_at),AND(tblMilestones[[#This Row],[status]]="missed",tblMilestones[[#This Row],[target_date]]&"T23:59:59Z">=event_reconciliation_from_at)),"logged","not_required_or_before_window"))))
```

### Phases and Gates / `tblGateAssessments`

#### `tblGateAssessments[outcome_check]`

| Item | Value |
|---|---|
| Workbook tab | Phases and Gates |
| Table | `tblGateAssessments` |
| Field | `outcome_check` (R3 helper, not exported) |
| Authority | `reproduces_r1_rule` |
| Purpose | Checks the recorded outcome is pass, pass_with_conditions, or hold (standard). It never chooses an outcome. |
| R1 source rule or config | standard/lifecycle-terms.yaml (gate_outcomes) |
| Input fields | `gate_assessment_id`, `lookup_type`, `key`, `outcome` |
| Edge cases | invalid_outcome. |
| Expected synthetic result | valid 1 |
| Portability | Functions: COUNTIFS, IF (all in the portable set). Uses Excel Table structured references; recalculation verified in LibreOffice Calc 24.2, not yet in Excel itself. |

```text
=IF(tblGateAssessments[[#This Row],[gate_assessment_id]]="","",IF(COUNTIFS(tblLookupEntries[lookup_type],"gate_outcome",tblLookupEntries[key],tblGateAssessments[[#This Row],[outcome]])>0,"valid","invalid_outcome"))
```

#### `tblGateAssessments[assessor_check]`

| Item | Value |
|---|---|
| Workbook tab | Phases and Gates |
| Table | `tblGateAssessments` |
| Field | `assessor_check` (R3 helper, not exported) |
| Authority | `reproduces_r1_rule` |
| Purpose | Checks a named person (PER-) recorded the outcome. |
| R1 source rule or config | schemas/gate-assessment.schema.json (assessor_person_id) |
| Input fields | `gate_assessment_id`, `assessor_person_id` |
| Edge cases | not_a_person for any other ID. |
| Expected synthetic result | named_person 1 |
| Portability | Functions: IF, LEFT (all in the portable set). Uses Excel Table structured references; recalculation verified in LibreOffice Calc 24.2, not yet in Excel itself. |

```text
=IF(tblGateAssessments[[#This Row],[gate_assessment_id]]="","",IF(LEFT(tblGateAssessments[[#This Row],[assessor_person_id]],4)="PER-","named_person","not_a_person"))
```

#### `tblGateAssessments[reference_check]`

| Item | Value |
|---|---|
| Workbook tab | Phases and Gates |
| Table | `tblGateAssessments` |
| Field | `reference_check` (R3 helper, not exported) |
| Authority | `r3_workbook_validation` |
| Purpose | Checks the phase exists in the project and the gate belongs to that phase. |
| R1 source rule or config | None: R3 view over R1 records |
| Input fields | `gate_assessment_id`, `phase_id`, `project_id`, `lookup_type`, `key`, `gate_id`, `display_value`, `lifecycle_phase_key` |
| Edge cases | orphan_phase or gate_phase_mismatch. |
| Expected synthetic result | valid 1 |
| Portability | Functions: COUNTIFS, IF, INDEX, MATCH (all in the portable set). Uses Excel Table structured references; recalculation verified in LibreOffice Calc 24.2, not yet in Excel itself. |

```text
=IF(tblGateAssessments[[#This Row],[gate_assessment_id]]="","",IF(COUNTIFS(tblPhases[phase_id],tblGateAssessments[[#This Row],[phase_id]],tblPhases[project_id],tblGateAssessments[[#This Row],[project_id]])=0,"orphan_phase",IF(COUNTIFS(tblLookupEntries[lookup_type],"gate_id",tblLookupEntries[key],tblGateAssessments[[#This Row],[gate_id]],tblLookupEntries[display_value],INDEX(tblPhases[lifecycle_phase_key],MATCH(tblGateAssessments[[#This Row],[phase_id]],tblPhases[phase_id],0)))=0,"gate_phase_mismatch","valid")))
```

#### `tblGateAssessments[event_evidence]`

| Item | Value |
|---|---|
| Workbook tab | Phases and Gates |
| Table | `tblGateAssessments` |
| Field | `event_evidence` (R3 helper, not exported) |
| Authority | `r3_workbook_validation` |
| Purpose | Reconciles the assessment against the Event Log. |
| R1 source rule or config | None: R3 view over R1 records |
| Input fields | `gate_assessment_id`, `assessed_at`, `subject_id`, `event_type`, `event_reconciliation_from_at` |
| Edge cases | before_window for older assessments. |
| Expected synthetic result | logged 1 |
| Portability | Functions: AND, COUNTIFS, IF, OR (all in the portable set). Uses Excel Table structured references; recalculation verified in LibreOffice Calc 24.2, not yet in Excel itself. |

```text
=IF(tblGateAssessments[[#This Row],[gate_assessment_id]]="","",IF(AND(TRUE,tblGateAssessments[[#This Row],[assessed_at]]>=event_reconciliation_from_at,COUNTIFS(tblEventLog[subject_id],tblGateAssessments[[#This Row],[gate_assessment_id]],tblEventLog[event_type],"gate.assessed")=0),"missing:gate.assessed",IF(OR(AND(TRUE,tblGateAssessments[[#This Row],[assessed_at]]>=event_reconciliation_from_at)),"logged","before_window")))
```

### Tasks / `tblTasks`

#### `tblTasks[due_state]`

| Item | Value |
|---|---|
| Workbook tab | Tasks |
| Table | `tblTasks` |
| Field | `due_state` (R3 helper, not exported) |
| Authority | `r3_workbook_validation` |
| Purpose | Task due state as of calculation_as_of_at. |
| R1 source rule or config | None: R3 view over R1 records |
| Input fields | `task_id`, `planned_due_date`, `status`, `completed_at`, `calculation_as_of_at` |
| Edge cases | Blank due date gives no_due_date; blocked shows blocked even when past due; completed compares the completion date with the due date. |
| Expected synthetic result | completed_on_time 13, open_not_due 8, completed_late 6, blocked 1, overdue 2 |
| Portability | Functions: IF, LEFT (all in the portable set). Uses Excel Table structured references; recalculation verified in LibreOffice Calc 24.2, not yet in Excel itself. |

```text
=IF(tblTasks[[#This Row],[task_id]]="","",IF(tblTasks[[#This Row],[planned_due_date]]="","no_due_date",IF(tblTasks[[#This Row],[status]]="cancelled","cancelled",IF(tblTasks[[#This Row],[status]]="completed",IF(LEFT(tblTasks[[#This Row],[completed_at]],10)<=tblTasks[[#This Row],[planned_due_date]],"completed_on_time","completed_late"),IF(tblTasks[[#This Row],[status]]="blocked","blocked",IF(tblTasks[[#This Row],[planned_due_date]]<LEFT(calculation_as_of_at,10),"overdue","open_not_due"))))))
```

#### `tblTasks[predecessor_reference_valid]`

| Item | Value |
|---|---|
| Workbook tab | Tasks |
| Table | `tblTasks` |
| Field | `predecessor_reference_valid` (R3 helper, not exported) |
| Authority | `r3_workbook_validation` |
| Purpose | Checks every predecessor ID resolves to a task in this workbook. |
| R1 source rule or config | None: R3 view over R1 records |
| Input fields | `task_id`, `predecessor_task_ids` |
| Edge cases | Counts listed IDs (semicolons plus one) against IDs found; IDs are fixed length, so one cannot match inside another. |
| Expected synthetic result | no_predecessor 4, valid 26 |
| Portability | Functions: IF, ISNUMBER, LEN, SEARCH, SUBSTITUTE, SUMPRODUCT (all in the portable set). Uses Excel Table structured references; recalculation verified in LibreOffice Calc 24.2, not yet in Excel itself. |

```text
=IF(tblTasks[[#This Row],[task_id]]="","",IF(tblTasks[[#This Row],[predecessor_task_ids]]="","no_predecessor",IF(SUMPRODUCT((tblTasks[task_id]<>"")*ISNUMBER(SEARCH(tblTasks[task_id],tblTasks[[#This Row],[predecessor_task_ids]])))=LEN(tblTasks[[#This Row],[predecessor_task_ids]])-LEN(SUBSTITUTE(tblTasks[[#This Row],[predecessor_task_ids]],";",""))+1,"valid","invalid")))
```

#### `tblTasks[reference_check]`

| Item | Value |
|---|---|
| Workbook tab | Tasks |
| Table | `tblTasks` |
| Field | `reference_check` (R3 helper, not exported) |
| Authority | `r3_workbook_validation` |
| Purpose | Checks project, phase, and milestone references resolve within the same project. |
| R1 source rule or config | None: R3 view over R1 records |
| Input fields | `task_id`, `project_id`, `phase_id`, `milestone_id` |
| Edge cases | orphan_project, orphan_phase, or orphan_milestone. |
| Expected synthetic result | valid 30 |
| Portability | Functions: AND, COUNTIF, COUNTIFS, IF (all in the portable set). Uses Excel Table structured references; recalculation verified in LibreOffice Calc 24.2, not yet in Excel itself. |

```text
=IF(tblTasks[[#This Row],[task_id]]="","",IF(COUNTIF(tblProjects[project_id],tblTasks[[#This Row],[project_id]])=0,"orphan_project",IF(COUNTIFS(tblPhases[phase_id],tblTasks[[#This Row],[phase_id]],tblPhases[project_id],tblTasks[[#This Row],[project_id]])=0,"orphan_phase",IF(AND(tblTasks[[#This Row],[milestone_id]]<>"",COUNTIFS(tblMilestones[milestone_id],tblTasks[[#This Row],[milestone_id]],tblMilestones[project_id],tblTasks[[#This Row],[project_id]])=0),"orphan_milestone","valid"))))
```

#### `tblTasks[event_evidence]`

| Item | Value |
|---|---|
| Workbook tab | Tasks |
| Table | `tblTasks` |
| Field | `event_evidence` (R3 helper, not exported) |
| Authority | `r3_workbook_validation` |
| Purpose | Reconciles completed (inside the window) and blocked tasks against the Event Log. |
| R1 source rule or config | None: R3 view over R1 records |
| Input fields | `task_id`, `status`, `subject_id`, `event_type`, `completed_at`, `event_reconciliation_from_at` |
| Edge cases | Blocked tasks always need a status event. |
| Expected synthetic result | logged 2, missing:task.status_changed 13, not_required_or_before_window 15 |
| Portability | Functions: AND, COUNTIFS, IF, OR (all in the portable set). Uses Excel Table structured references; recalculation verified in LibreOffice Calc 24.2, not yet in Excel itself. |

```text
=IF(tblTasks[[#This Row],[task_id]]="","",IF(tblTasks[[#This Row],[status]]="blocked",IF(COUNTIFS(tblEventLog[subject_id],tblTasks[[#This Row],[task_id]],tblEventLog[event_type],"task.status_changed")=0,"missing:task.status_changed","logged"),IF(AND(tblTasks[[#This Row],[status]]="completed",tblTasks[[#This Row],[completed_at]]>=event_reconciliation_from_at,COUNTIFS(tblEventLog[subject_id],tblTasks[[#This Row],[task_id]],tblEventLog[event_type],"task.status_changed")=0),"missing:task.status_changed",IF(OR(AND(tblTasks[[#This Row],[status]]="completed",tblTasks[[#This Row],[completed_at]]>=event_reconciliation_from_at)),"logged","not_required_or_before_window"))))
```

### Requests and Handoffs / `tblRequests`

#### `tblRequests[status_check]`

| Item | Value |
|---|---|
| Workbook tab | Requests and Handoffs |
| Table | `tblRequests` |
| Field | `status_check` (R3 helper, not exported) |
| Authority | `reproduces_r1_rule` |
| Purpose | Checks the status is one of the nine R1 request statuses. |
| R1 source rule or config | config/request-state-machine.yaml (statuses) |
| Input fields | `request_id`, `lookup_type`, `key`, `status` |
| Edge cases | invalid_status. |
| Expected synthetic result | valid 8 |
| Portability | Functions: COUNTIFS, IF (all in the portable set). Uses Excel Table structured references; recalculation verified in LibreOffice Calc 24.2, not yet in Excel itself. |

```text
=IF(tblRequests[[#This Row],[request_id]]="","",IF(COUNTIFS(tblLookupEntries[lookup_type],"request_status",tblLookupEntries[key],tblRequests[[#This Row],[status]])>0,"valid","invalid_status"))
```

#### `tblRequests[escalation_rule_id]`

| Item | Value |
|---|---|
| Workbook tab | Requests and Handoffs |
| Table | `tblRequests` |
| Field | `escalation_rule_id` (R3 helper, not exported) |
| Authority | `reproduces_r1_rule` |
| Purpose | The enabled R1 escalation rule whose trigger is the request's current status. |
| R1 source rule or config | config/sla-rules.yaml (rules.trigger, rules.action) |
| Input fields | `request_id`, `rule_id`, `status`, `match_key` |
| Edge cases | Blank when no rule applies to the status. |
| Expected synthetic result | (blank) 5, RUL-000003 1, RUL-000002 1, RUL-000001 1 |
| Portability | Functions: IF, IFERROR, INDEX, MATCH (all in the portable set). Uses Excel Table structured references; recalculation verified in LibreOffice Calc 24.2, not yet in Excel itself. |

```text
=IF(tblRequests[[#This Row],[request_id]]="","",IFERROR(INDEX(tblEscalationRules[rule_id],MATCH("request|"&tblRequests[[#This Row],[status]],tblEscalationRules[match_key],0)),""))
```

#### `tblRequests[escalation_due_check]`

| Item | Value |
|---|---|
| Workbook tab | Requests and Handoffs |
| Table | `tblRequests` |
| Field | `escalation_due_check` (R3 helper, not exported) |
| Authority | `reproduces_r1_rule` |
| Purpose | Recomputes escalation_due_at = status_changed_at + the rule's target duration (R1 config/sla-rules.yaml) and compares. |
| R1 source rule or config | config/sla-rules.yaml (rules.target_duration) |
| Input fields | `request_id`, `escalation_rule_id`, `escalation_due_at`, `status_changed_at`, `duration_hours`, `rule_id` |
| Edge cases | Tolerance under 9 seconds absorbs floating-point date arithmetic. |
| Expected synthetic result | consistent 8 |
| Portability | Functions: ABS, DATEVALUE, IF, INDEX, LEFT, MATCH, MID, TIMEVALUE (all in the portable set). Uses Excel Table structured references; recalculation verified in LibreOffice Calc 24.2, not yet in Excel itself. DATEVALUE and TIMEVALUE read ISO text; locales that do not accept ISO dates are a documented limitation. |

```text
=IF(tblRequests[[#This Row],[request_id]]="","",IF(tblRequests[[#This Row],[escalation_rule_id]]="",IF(tblRequests[[#This Row],[escalation_due_at]]="","consistent","unexpected_escalation_due_at"),IF(tblRequests[[#This Row],[escalation_due_at]]="","missing_escalation_due_at",IF(ABS((DATEVALUE(LEFT(tblRequests[[#This Row],[status_changed_at]],10))+TIMEVALUE(MID(tblRequests[[#This Row],[status_changed_at]],12,8)))+INDEX(tblEscalationRules[duration_hours],MATCH(tblRequests[[#This Row],[escalation_rule_id]],tblEscalationRules[rule_id],0))/24-(DATEVALUE(LEFT(tblRequests[[#This Row],[escalation_due_at]],10))+TIMEVALUE(MID(tblRequests[[#This Row],[escalation_due_at]],12,8))))<0.0001,"consistent","mismatch"))))
```

#### `tblRequests[escalation_due_state]`

| Item | Value |
|---|---|
| Workbook tab | Requests and Handoffs |
| Table | `tblRequests` |
| Field | `escalation_due_state` (R3 helper, not exported) |
| Authority | `r3_workbook_validation` |
| Purpose | Whether the request's escalation time has passed as of calculation_as_of_at. |
| R1 source rule or config | None: R3 view over R1 records |
| Input fields | `request_id`, `status`, `escalation_due_at`, `calculation_as_of_at` |
| Edge cases | closed, no_escalation_timer, escalation_due (due at or before the as-of time), due_later. |
| Expected synthetic result | no_escalation_timer 4, escalation_due 1, due_later 2, closed 1 |
| Portability | Functions: IF (all in the portable set). Uses Excel Table structured references; recalculation verified in LibreOffice Calc 24.2, not yet in Excel itself. |

```text
=IF(tblRequests[[#This Row],[request_id]]="","",IF(tblRequests[[#This Row],[status]]="closed","closed",IF(tblRequests[[#This Row],[escalation_due_at]]="","no_escalation_timer",IF(tblRequests[[#This Row],[escalation_due_at]]<=calculation_as_of_at,"escalation_due","due_later"))))
```

#### `tblRequests[reference_check]`

| Item | Value |
|---|---|
| Workbook tab | Requests and Handoffs |
| Table | `tblRequests` |
| Field | `reference_check` (R3 helper, not exported) |
| Authority | `r3_workbook_validation` |
| Purpose | Checks that the referenced project exist in this workbook. |
| R1 source rule or config | None: R3 view over R1 records |
| Input fields | `request_id`, `project_id` |
| Edge cases | Returns orphan_project or orphan_phase when a reference does not resolve. |
| Expected synthetic result | valid 8 |
| Portability | Functions: COUNTIF, IF (all in the portable set). Uses Excel Table structured references; recalculation verified in LibreOffice Calc 24.2, not yet in Excel itself. |

```text
=IF(tblRequests[[#This Row],[request_id]]="","",IF(COUNTIF(tblProjects[project_id],tblRequests[[#This Row],[project_id]])=0,"orphan_project","valid"))
```

#### `tblRequests[event_evidence]`

| Item | Value |
|---|---|
| Workbook tab | Requests and Handoffs |
| Table | `tblRequests` |
| Field | `event_evidence` (R3 helper, not exported) |
| Authority | `r3_workbook_validation` |
| Purpose | Reconciles submission and the latest status change against the Event Log. |
| R1 source rule or config | None: R3 view over R1 records |
| Input fields | `request_id`, `submitted_at`, `subject_id`, `event_type`, `status`, `status_changed_at`, `event_reconciliation_from_at` |
| Edge cases | Submission is checked first. |
| Expected synthetic result | missing:request.submitted 6, logged 2 |
| Portability | Functions: AND, COUNTIFS, IF, OR (all in the portable set). Uses Excel Table structured references; recalculation verified in LibreOffice Calc 24.2, not yet in Excel itself. |

```text
=IF(tblRequests[[#This Row],[request_id]]="","",IF(AND(TRUE,tblRequests[[#This Row],[submitted_at]]>=event_reconciliation_from_at,COUNTIFS(tblEventLog[subject_id],tblRequests[[#This Row],[request_id]],tblEventLog[event_type],"request.submitted")=0),"missing:request.submitted",IF(AND(tblRequests[[#This Row],[status]]<>"submitted",tblRequests[[#This Row],[status_changed_at]]>=event_reconciliation_from_at,COUNTIFS(tblEventLog[subject_id],tblRequests[[#This Row],[request_id]],tblEventLog[event_type],"request.status_changed")=0),"missing:request.status_changed",IF(OR(AND(TRUE,tblRequests[[#This Row],[submitted_at]]>=event_reconciliation_from_at),AND(tblRequests[[#This Row],[status]]<>"submitted",tblRequests[[#This Row],[status_changed_at]]>=event_reconciliation_from_at)),"logged","before_window"))))
```

### Requests and Handoffs / `tblHandoffs`

#### `tblHandoffs[status_check]`

| Item | Value |
|---|---|
| Workbook tab | Requests and Handoffs |
| Table | `tblHandoffs` |
| Field | `status_check` (R3 helper, not exported) |
| Authority | `reproduces_r1_rule` |
| Purpose | Checks the status is an R1 handoff status. |
| R1 source rule or config | schemas/handoff.schema.json (status) |
| Input fields | `handoff_id`, `lookup_type`, `key`, `status` |
| Edge cases | invalid_status. |
| Expected synthetic result | valid 1 |
| Portability | Functions: COUNTIFS, IF (all in the portable set). Uses Excel Table structured references; recalculation verified in LibreOffice Calc 24.2, not yet in Excel itself. |

```text
=IF(tblHandoffs[[#This Row],[handoff_id]]="","",IF(COUNTIFS(tblLookupEntries[lookup_type],"handoff_status",tblLookupEntries[key],tblHandoffs[[#This Row],[status]])>0,"valid","invalid_status"))
```

#### `tblHandoffs[acceptance_check]`

| Item | Value |
|---|---|
| Workbook tab | Requests and Handoffs |
| Table | `tblHandoffs` |
| Field | `acceptance_check` (R3 helper, not exported) |
| Authority | `reproduces_r1_rule` |
| Purpose | Checks an accepted handoff names the person who accepted it (R1 handoff schema). |
| R1 source rule or config | schemas/handoff.schema.json (accepted status rule) |
| Input fields | `handoff_id`, `status`, `acceptance_person_id`, `accepted_at` |
| Edge cases | missing_named_acceptance. |
| Expected synthetic result | named_acceptance 1 |
| Portability | Functions: AND, IF, LEFT (all in the portable set). Uses Excel Table structured references; recalculation verified in LibreOffice Calc 24.2, not yet in Excel itself. |

```text
=IF(tblHandoffs[[#This Row],[handoff_id]]="","",IF(tblHandoffs[[#This Row],[status]]="accepted",IF(AND(LEFT(tblHandoffs[[#This Row],[acceptance_person_id]],4)="PER-",tblHandoffs[[#This Row],[accepted_at]]<>""),"named_acceptance","missing_named_acceptance"),"not_accepted"))
```

#### `tblHandoffs[reference_check]`

| Item | Value |
|---|---|
| Workbook tab | Requests and Handoffs |
| Table | `tblHandoffs` |
| Field | `reference_check` (R3 helper, not exported) |
| Authority | `r3_workbook_validation` |
| Purpose | Checks that the referenced project exist in this workbook. |
| R1 source rule or config | None: R3 view over R1 records |
| Input fields | `handoff_id`, `project_id` |
| Edge cases | Returns orphan_project or orphan_phase when a reference does not resolve. |
| Expected synthetic result | valid 1 |
| Portability | Functions: COUNTIF, IF (all in the portable set). Uses Excel Table structured references; recalculation verified in LibreOffice Calc 24.2, not yet in Excel itself. |

```text
=IF(tblHandoffs[[#This Row],[handoff_id]]="","",IF(COUNTIF(tblProjects[project_id],tblHandoffs[[#This Row],[project_id]])=0,"orphan_project","valid"))
```

#### `tblHandoffs[event_evidence]`

| Item | Value |
|---|---|
| Workbook tab | Requests and Handoffs |
| Table | `tblHandoffs` |
| Field | `event_evidence` (R3 helper, not exported) |
| Authority | `r3_workbook_validation` |
| Purpose | Reconciles accepted handoffs against the Event Log. |
| R1 source rule or config | None: R3 view over R1 records |
| Input fields | `handoff_id`, `status`, `accepted_at`, `subject_id`, `event_type`, `event_reconciliation_from_at` |
| Edge cases | Only accepted handoffs need an event. |
| Expected synthetic result | logged 1 |
| Portability | Functions: AND, COUNTIFS, IF, OR (all in the portable set). Uses Excel Table structured references; recalculation verified in LibreOffice Calc 24.2, not yet in Excel itself. |

```text
=IF(tblHandoffs[[#This Row],[handoff_id]]="","",IF(AND(tblHandoffs[[#This Row],[status]]="accepted",tblHandoffs[[#This Row],[accepted_at]]>=event_reconciliation_from_at,COUNTIFS(tblEventLog[subject_id],tblHandoffs[[#This Row],[handoff_id]],tblEventLog[event_type],"handoff.completed")=0),"missing:handoff.completed",IF(OR(AND(tblHandoffs[[#This Row],[status]]="accepted",tblHandoffs[[#This Row],[accepted_at]]>=event_reconciliation_from_at)),"logged","not_required_or_before_window")))
```

### Risks and Issues / `tblRisks`

#### `tblRisks[risk_score]`

| Item | Value |
|---|---|
| Workbook tab | Risks and Issues |
| Table | `tblRisks` |
| Field | `risk_score` (R1 field) |
| Authority | `reproduces_r1_rule` |
| Purpose | risk_score = likelihood x impact on the configured scale (R1 config/risk-rules.yaml). |
| R1 source rule or config | config/risk-rules.yaml (formula likelihood_times_impact; likelihood_values, impact_values) |
| Input fields | `risk_id`, `likelihood`, `impact`, `risk_likelihood_min`, `risk_likelihood_max`, `risk_impact_min`, `risk_impact_max` |
| Edge cases | invalid_scale_value for blanks, fractions, or values outside the R1 scale. |
| Expected synthetic result | 6 1, 12 2, 9 1, 8 1, 10 1 |
| Portability | Functions: AND, IF, INT, ISNUMBER (all in the portable set). Uses Excel Table structured references; recalculation verified in LibreOffice Calc 24.2, not yet in Excel itself. |

```text
=IF(tblRisks[[#This Row],[risk_id]]="","",IF(AND(ISNUMBER(tblRisks[[#This Row],[likelihood]]),ISNUMBER(tblRisks[[#This Row],[impact]])),IF(AND(tblRisks[[#This Row],[likelihood]]=INT(tblRisks[[#This Row],[likelihood]]),tblRisks[[#This Row],[impact]]=INT(tblRisks[[#This Row],[impact]]),tblRisks[[#This Row],[likelihood]]>=risk_likelihood_min,tblRisks[[#This Row],[likelihood]]<=risk_likelihood_max,tblRisks[[#This Row],[impact]]>=risk_impact_min,tblRisks[[#This Row],[impact]]<=risk_impact_max),tblRisks[[#This Row],[likelihood]]*tblRisks[[#This Row],[impact]],"invalid_scale_value"),"invalid_scale_value"))
```

#### `tblRisks[risk_band]`

| Item | Value |
|---|---|
| Workbook tab | Risks and Issues |
| Table | `tblRisks` |
| Field | `risk_band` (R3 helper, not exported) |
| Authority | `reproduces_r1_rule` |
| Purpose | The R1 band whose score range contains risk_score. |
| R1 source rule or config | config/risk-rules.yaml (bands) |
| Input fields | `risk_id`, `risk_score`, `band`, `min_score` |
| Edge cases | invalid_scale_value when the score is invalid. |
| Expected synthetic result | moderate 3, high 3 |
| Portability | Functions: IF, IFERROR, INDEX, ISNUMBER, MATCH (all in the portable set). Uses Excel Table structured references; recalculation verified in LibreOffice Calc 24.2, not yet in Excel itself. |

```text
=IF(tblRisks[[#This Row],[risk_id]]="","",IF(ISNUMBER(tblRisks[[#This Row],[risk_score]]),IFERROR(INDEX(tblRiskBands[band],MATCH(tblRisks[[#This Row],[risk_score]],tblRiskBands[min_score],1)),"no_band"),"invalid_scale_value"))
```

#### `tblRisks[risk_severity]`

| Item | Value |
|---|---|
| Workbook tab | Risks and Issues |
| Table | `tblRisks` |
| Field | `risk_severity` (R3 helper, not exported) |
| Authority | `reproduces_r1_rule` |
| Purpose | The severity R1 assigns to the band (carried by risk.logged). |
| R1 source rule or config | config/risk-rules.yaml (bands.severity) |
| Input fields | `risk_id`, `risk_score`, `severity`, `min_score` |
| Edge cases | Same as risk_band. |
| Expected synthetic result | sev3 3, sev2 3 |
| Portability | Functions: IF, IFERROR, INDEX, ISNUMBER, MATCH (all in the portable set). Uses Excel Table structured references; recalculation verified in LibreOffice Calc 24.2, not yet in Excel itself. |

```text
=IF(tblRisks[[#This Row],[risk_id]]="","",IF(ISNUMBER(tblRisks[[#This Row],[risk_score]]),IFERROR(INDEX(tblRiskBands[severity],MATCH(tblRisks[[#This Row],[risk_score]],tblRiskBands[min_score],1)),"no_band"),"invalid_scale_value"))
```

#### `tblRisks[reference_check]`

| Item | Value |
|---|---|
| Workbook tab | Risks and Issues |
| Table | `tblRisks` |
| Field | `reference_check` (R3 helper, not exported) |
| Authority | `r3_workbook_validation` |
| Purpose | Checks that the referenced project and phase (same project) exist in this workbook. |
| R1 source rule or config | None: R3 view over R1 records |
| Input fields | `risk_id`, `project_id`, `phase_id` |
| Edge cases | Returns orphan_project or orphan_phase when a reference does not resolve. |
| Expected synthetic result | valid 6 |
| Portability | Functions: COUNTIF, COUNTIFS, IF (all in the portable set). Uses Excel Table structured references; recalculation verified in LibreOffice Calc 24.2, not yet in Excel itself. |

```text
=IF(tblRisks[[#This Row],[risk_id]]="","",IF(COUNTIF(tblProjects[project_id],tblRisks[[#This Row],[project_id]])=0,"orphan_project",IF(COUNTIFS(tblPhases[phase_id],tblRisks[[#This Row],[phase_id]],tblPhases[project_id],tblRisks[[#This Row],[project_id]])=0,"orphan_phase","valid")))
```

#### `tblRisks[event_evidence]`

| Item | Value |
|---|---|
| Workbook tab | Risks and Issues |
| Table | `tblRisks` |
| Field | `event_evidence` (R3 helper, not exported) |
| Authority | `r3_workbook_validation` |
| Purpose | Reconciles risk logging against the Event Log. |
| R1 source rule or config | None: R3 view over R1 records |
| Input fields | `risk_id`, `identified_at`, `subject_id`, `event_type`, `event_reconciliation_from_at` |
| Edge cases | before_window for older risks. |
| Expected synthetic result | logged 2, missing:risk.logged 3, before_window 1 |
| Portability | Functions: AND, COUNTIFS, IF, OR (all in the portable set). Uses Excel Table structured references; recalculation verified in LibreOffice Calc 24.2, not yet in Excel itself. |

```text
=IF(tblRisks[[#This Row],[risk_id]]="","",IF(AND(TRUE,tblRisks[[#This Row],[identified_at]]>=event_reconciliation_from_at,COUNTIFS(tblEventLog[subject_id],tblRisks[[#This Row],[risk_id]],tblEventLog[event_type],"risk.logged")=0),"missing:risk.logged",IF(OR(AND(TRUE,tblRisks[[#This Row],[identified_at]]>=event_reconciliation_from_at)),"logged","before_window")))
```

### Risks and Issues / `tblIssues`

#### `tblIssues[severity_check]`

| Item | Value |
|---|---|
| Workbook tab | Risks and Issues |
| Table | `tblIssues` |
| Field | `severity_check` (R3 helper, not exported) |
| Authority | `reproduces_r1_rule` |
| Purpose | Checks severity is sev1 to sev4 (R1 standard/severity-scale.yaml). |
| R1 source rule or config | standard/severity-scale.yaml |
| Input fields | `issue_id`, `lookup_type`, `key`, `severity` |
| Edge cases | invalid_severity. |
| Expected synthetic result | valid 5 |
| Portability | Functions: COUNTIFS, IF (all in the portable set). Uses Excel Table structured references; recalculation verified in LibreOffice Calc 24.2, not yet in Excel itself. |

```text
=IF(tblIssues[[#This Row],[issue_id]]="","",IF(COUNTIFS(tblLookupEntries[lookup_type],"severity",tblLookupEntries[key],tblIssues[[#This Row],[severity]])>0,"valid","invalid_severity"))
```

#### `tblIssues[reference_check]`

| Item | Value |
|---|---|
| Workbook tab | Risks and Issues |
| Table | `tblIssues` |
| Field | `reference_check` (R3 helper, not exported) |
| Authority | `r3_workbook_validation` |
| Purpose | Checks that the referenced project and phase (same project) exist in this workbook. |
| R1 source rule or config | None: R3 view over R1 records |
| Input fields | `issue_id`, `project_id`, `phase_id` |
| Edge cases | Returns orphan_project or orphan_phase when a reference does not resolve. |
| Expected synthetic result | valid 5 |
| Portability | Functions: COUNTIF, COUNTIFS, IF (all in the portable set). Uses Excel Table structured references; recalculation verified in LibreOffice Calc 24.2, not yet in Excel itself. |

```text
=IF(tblIssues[[#This Row],[issue_id]]="","",IF(COUNTIF(tblProjects[project_id],tblIssues[[#This Row],[project_id]])=0,"orphan_project",IF(COUNTIFS(tblPhases[phase_id],tblIssues[[#This Row],[phase_id]],tblPhases[project_id],tblIssues[[#This Row],[project_id]])=0,"orphan_phase","valid")))
```

#### `tblIssues[event_evidence]`

| Item | Value |
|---|---|
| Workbook tab | Risks and Issues |
| Table | `tblIssues` |
| Field | `event_evidence` (R3 helper, not exported) |
| Authority | `r3_workbook_validation` |
| Purpose | Reconciles issue logging and resolution against the Event Log. |
| R1 source rule or config | None: R3 view over R1 records |
| Input fields | `issue_id`, `opened_at`, `subject_id`, `event_type`, `status`, `resolved_at`, `event_reconciliation_from_at` |
| Edge cases | Logging is checked first. |
| Expected synthetic result | missing:issue.logged 3, logged 2 |
| Portability | Functions: AND, COUNTIFS, IF, OR (all in the portable set). Uses Excel Table structured references; recalculation verified in LibreOffice Calc 24.2, not yet in Excel itself. |

```text
=IF(tblIssues[[#This Row],[issue_id]]="","",IF(AND(TRUE,tblIssues[[#This Row],[opened_at]]>=event_reconciliation_from_at,COUNTIFS(tblEventLog[subject_id],tblIssues[[#This Row],[issue_id]],tblEventLog[event_type],"issue.logged")=0),"missing:issue.logged",IF(AND(OR(tblIssues[[#This Row],[status]]="resolved",tblIssues[[#This Row],[status]]="closed"),tblIssues[[#This Row],[resolved_at]]>=event_reconciliation_from_at,COUNTIFS(tblEventLog[subject_id],tblIssues[[#This Row],[issue_id]],tblEventLog[event_type],"issue.resolved")=0),"missing:issue.resolved",IF(OR(AND(TRUE,tblIssues[[#This Row],[opened_at]]>=event_reconciliation_from_at),AND(OR(tblIssues[[#This Row],[status]]="resolved",tblIssues[[#This Row],[status]]="closed"),tblIssues[[#This Row],[resolved_at]]>=event_reconciliation_from_at)),"logged","before_window"))))
```

### Readiness Scorecard / `tblReadiness`

#### `tblReadiness[weight]`

| Item | Value |
|---|---|
| Workbook tab | Readiness Scorecard |
| Table | `tblReadiness` |
| Field | `weight` (R1 field) |
| Authority | `reproduces_r1_rule` |
| Purpose | The category weight from R1 config/readiness-weights.yaml (mirrored on Lookups). |
| R1 source rule or config | config/readiness-weights.yaml (categories.weight) |
| Input fields | `readiness_entry_id`, `weight`, `category` |
| Edge cases | unknown_category when the category is not one of the six. |
| Expected synthetic result | 15 9, 25 3, 20 3, 10 3 |
| Portability | Functions: IF, IFERROR, INDEX, MATCH (all in the portable set). Uses Excel Table structured references; recalculation verified in LibreOffice Calc 24.2, not yet in Excel itself. |

```text
=IF(tblReadiness[[#This Row],[readiness_entry_id]]="","",IFERROR(INDEX(tblReadinessWeights[weight],MATCH(tblReadiness[[#This Row],[category]],tblReadinessWeights[category],0)),"unknown_category"))
```

#### `tblReadiness[achieved_rate]`

| Item | Value |
|---|---|
| Workbook tab | Readiness Scorecard |
| Table | `tblReadiness` |
| Field | `achieved_rate` (R1 field) |
| Authority | `reproduces_r1_rule` |
| Purpose | achieved_rate = criteria_met_count / criteria_total_count (R1). |
| R1 source rule or config | config/readiness-weights.yaml (calculation) |
| Input fields | `readiness_entry_id`, `criteria_total_count`, `criteria_met_count` |
| Edge cases | invalid_criteria_counts when total is below 1 or met is outside 0 to total; never divides by zero. |
| Expected synthetic result | 0.5 1, 0.25 3, 0 5, 0.75 4, 0.4 1, 1 4 |
| Portability | Functions: AND, IF, ISNUMBER (all in the portable set). Uses Excel Table structured references; recalculation verified in LibreOffice Calc 24.2, not yet in Excel itself. |

```text
=IF(tblReadiness[[#This Row],[readiness_entry_id]]="","",IF(AND(ISNUMBER(tblReadiness[[#This Row],[criteria_total_count]]),ISNUMBER(tblReadiness[[#This Row],[criteria_met_count]])),IF(AND(tblReadiness[[#This Row],[criteria_total_count]]>=1,tblReadiness[[#This Row],[criteria_met_count]]>=0,tblReadiness[[#This Row],[criteria_met_count]]<=tblReadiness[[#This Row],[criteria_total_count]]),tblReadiness[[#This Row],[criteria_met_count]]/tblReadiness[[#This Row],[criteria_total_count]],"invalid_criteria_counts"),"invalid_criteria_counts"))
```

#### `tblReadiness[category_score]`

| Item | Value |
|---|---|
| Workbook tab | Readiness Scorecard |
| Table | `tblReadiness` |
| Field | `category_score` (R1 field) |
| Authority | `reproduces_r1_rule` |
| Purpose | category_score = weight x achieved_rate, rounded half-up to 2 places (R1). |
| R1 source rule or config | config/readiness-weights.yaml (calculation) |
| Input fields | `readiness_entry_id`, `weighted_result` |
| Edge cases | Blank when the weight or rate is invalid. |
| Expected synthetic result | 18 values, total 145 |
| Portability | Functions: IF, ISNUMBER, ROUND (all in the portable set). Uses Excel Table structured references; recalculation verified in LibreOffice Calc 24.2, not yet in Excel itself. |

```text
=IF(tblReadiness[[#This Row],[readiness_entry_id]]="","",IF(ISNUMBER(tblReadiness[[#This Row],[weighted_result]]),ROUND(tblReadiness[[#This Row],[weighted_result]],2),""))
```

#### `tblReadiness[overall_score]`

| Item | Value |
|---|---|
| Workbook tab | Readiness Scorecard |
| Table | `tblReadiness` |
| Field | `overall_score` (R1 field) |
| Authority | `reproduces_r1_rule` |
| Purpose | overall_score = 100 x sum(weight x achieved_rate) / sum(weight) for the scorecard, rounded half-up to 2 places (R1). |
| R1 source rule or config | config/readiness-weights.yaml (calculation) |
| Input fields | `readiness_entry_id`, `readiness_scorecard_id`, `category_count_check`, `category`, `weighted_result`, `weight` |
| Edge cases | incomplete_scorecard unless the scorecard has exactly one row for each of the six categories; never divides by zero. |
| Expected synthetic result | 16.25 6, 37.5 6, 91.25 6 |
| Portability | Functions: COUNTIFS, IF, IFERROR, ROUND, ROWS, SUMIFS (all in the portable set). Uses Excel Table structured references; recalculation verified in LibreOffice Calc 24.2, not yet in Excel itself. |

```text
=IF(tblReadiness[[#This Row],[readiness_entry_id]]="","",IF(COUNTIFS(tblReadiness[readiness_scorecard_id],tblReadiness[[#This Row],[readiness_scorecard_id]],tblReadiness[category_count_check],"complete")<>ROWS(tblReadinessWeights[category]),"incomplete_scorecard",IFERROR(ROUND(100*SUMIFS(tblReadiness[weighted_result],tblReadiness[readiness_scorecard_id],tblReadiness[[#This Row],[readiness_scorecard_id]])/SUMIFS(tblReadiness[weight],tblReadiness[readiness_scorecard_id],tblReadiness[[#This Row],[readiness_scorecard_id]]),2),"incomplete_scorecard")))
```

#### `tblReadiness[incomplete_required_evidence_flag]`

| Item | Value |
|---|---|
| Workbook tab | Readiness Scorecard |
| Table | `tblReadiness` |
| Field | `incomplete_required_evidence_flag` (R1 field) |
| Authority | `reproduces_r1_rule` |
| Purpose | TRUE when any category of the scorecard lacks its required evidence (R1). |
| R1 source rule or config | config/readiness-weights.yaml (calculation) |
| Input fields | `readiness_entry_id`, `readiness_scorecard_id`, `required_evidence_complete_flag` |
| Edge cases | A high score with this flag TRUE is still incomplete. |
| Expected synthetic result | TRUE 18, FALSE 0 |
| Portability | Functions: COUNTIFS, IF (all in the portable set). Uses Excel Table structured references; recalculation verified in LibreOffice Calc 24.2, not yet in Excel itself. |

```text
=IF(tblReadiness[[#This Row],[readiness_entry_id]]="","",COUNTIFS(tblReadiness[readiness_scorecard_id],tblReadiness[[#This Row],[readiness_scorecard_id]],tblReadiness[required_evidence_complete_flag],FALSE)>0)
```

#### `tblReadiness[weighted_result]`

| Item | Value |
|---|---|
| Workbook tab | Readiness Scorecard |
| Table | `tblReadiness` |
| Field | `weighted_result` (R3 helper, not exported) |
| Authority | `reproduces_r1_rule` |
| Purpose | weight x achieved_rate before rounding; the overall score sums these (R1). |
| R1 source rule or config | config/readiness-weights.yaml (calculation) |
| Input fields | `readiness_entry_id`, `weight`, `achieved_rate` |
| Edge cases | Blank when an input is invalid. |
| Expected synthetic result | 18 values, total 145 |
| Portability | Functions: AND, IF, ISNUMBER (all in the portable set). Uses Excel Table structured references; recalculation verified in LibreOffice Calc 24.2, not yet in Excel itself. |

```text
=IF(tblReadiness[[#This Row],[readiness_entry_id]]="","",IF(AND(ISNUMBER(tblReadiness[[#This Row],[weight]]),ISNUMBER(tblReadiness[[#This Row],[achieved_rate]])),tblReadiness[[#This Row],[weight]]*tblReadiness[[#This Row],[achieved_rate]],""))
```

#### `tblReadiness[category_count_check]`

| Item | Value |
|---|---|
| Workbook tab | Readiness Scorecard |
| Table | `tblReadiness` |
| Field | `category_count_check` (R3 helper, not exported) |
| Authority | `r3_workbook_validation` |
| Purpose | Checks the scorecard has exactly one row for each R1 readiness category. |
| R1 source rule or config | None: R3 view over R1 records |
| Input fields | `readiness_entry_id`, `readiness_scorecard_id`, `category` |
| Edge cases | missing_or_extra_category, duplicate_category, unknown_category. |
| Expected synthetic result | complete 18 |
| Portability | Functions: COUNTIF, COUNTIFS, IF, ROWS (all in the portable set). Uses Excel Table structured references; recalculation verified in LibreOffice Calc 24.2, not yet in Excel itself. |

```text
=IF(tblReadiness[[#This Row],[readiness_entry_id]]="","",IF(COUNTIF(tblReadiness[readiness_scorecard_id],tblReadiness[[#This Row],[readiness_scorecard_id]])<>ROWS(tblReadinessWeights[category]),"missing_or_extra_category",IF(COUNTIFS(tblReadiness[readiness_scorecard_id],tblReadiness[[#This Row],[readiness_scorecard_id]],tblReadiness[category],tblReadiness[[#This Row],[category]])<>1,"duplicate_category",IF(COUNTIF(tblReadinessWeights[category],tblReadiness[[#This Row],[category]])=0,"unknown_category","complete"))))
```

### Readiness Scorecard / `tblReadinessSummary`

#### `tblReadinessSummary[project_id]`

| Item | Value |
|---|---|
| Workbook tab | Readiness Scorecard |
| Table | `tblReadinessSummary` |
| Field | `project_id` (R3 field) |
| Authority | `summarizes_r1_records` |
| Purpose | Project of the scorecard. |
| R1 source rule or config | None: R3 view over R1 records |
| Input fields | `readiness_scorecard_id`, `project_id` |
| Edge cases | scorecard_not_found. |
| Expected synthetic result | PRJ-000001 1, PRJ-000002 1, PRJ-000003 1 |
| Portability | Functions: IF, IFERROR, INDEX, MATCH (all in the portable set). Uses Excel Table structured references; recalculation verified in LibreOffice Calc 24.2, not yet in Excel itself. |

```text
=IF(tblReadinessSummary[[#This Row],[readiness_scorecard_id]]="","",IFERROR(INDEX(tblReadiness[project_id],MATCH(tblReadinessSummary[[#This Row],[readiness_scorecard_id]],tblReadiness[readiness_scorecard_id],0)),"scorecard_not_found")&"")
```

#### `tblReadinessSummary[assessment_purpose]`

| Item | Value |
|---|---|
| Workbook tab | Readiness Scorecard |
| Table | `tblReadinessSummary` |
| Field | `assessment_purpose` (R3 field) |
| Authority | `summarizes_r1_records` |
| Purpose | pre_assessment or launch_review. |
| R1 source rule or config | None: R3 view over R1 records |
| Input fields | `readiness_scorecard_id`, `assessment_purpose` |
| Edge cases | scorecard_not_found. |
| Expected synthetic result | pre_assessment 2, launch_review 1 |
| Portability | Functions: IF, IFERROR, INDEX, MATCH (all in the portable set). Uses Excel Table structured references; recalculation verified in LibreOffice Calc 24.2, not yet in Excel itself. |

```text
=IF(tblReadinessSummary[[#This Row],[readiness_scorecard_id]]="","",IFERROR(INDEX(tblReadiness[assessment_purpose],MATCH(tblReadinessSummary[[#This Row],[readiness_scorecard_id]],tblReadiness[readiness_scorecard_id],0)),"scorecard_not_found")&"")
```

#### `tblReadinessSummary[assessed_at]`

| Item | Value |
|---|---|
| Workbook tab | Readiness Scorecard |
| Table | `tblReadinessSummary` |
| Field | `assessed_at` (R3 field) |
| Authority | `summarizes_r1_records` |
| Purpose | When the scorecard was calculated. |
| R1 source rule or config | None: R3 view over R1 records |
| Input fields | `readiness_scorecard_id`, `assessed_at` |
| Edge cases | scorecard_not_found. |
| Expected synthetic result | 2026-10-01T15:00:00Z 1, 2026-10-01T16:00:00Z 1, 2026-10-02T15:00:00Z 1 |
| Portability | Functions: IF, IFERROR, INDEX, MATCH (all in the portable set). Uses Excel Table structured references; recalculation verified in LibreOffice Calc 24.2, not yet in Excel itself. |

```text
=IF(tblReadinessSummary[[#This Row],[readiness_scorecard_id]]="","",IFERROR(INDEX(tblReadiness[assessed_at],MATCH(tblReadinessSummary[[#This Row],[readiness_scorecard_id]],tblReadiness[readiness_scorecard_id],0)),"scorecard_not_found")&"")
```

#### `tblReadinessSummary[overall_score]`

| Item | Value |
|---|---|
| Workbook tab | Readiness Scorecard |
| Table | `tblReadinessSummary` |
| Field | `overall_score` (R3 field) |
| Authority | `reproduces_r1_rule` |
| Purpose | Overall readiness score (R1 calculation). |
| R1 source rule or config | config/readiness-weights.yaml (calculation) |
| Input fields | `readiness_scorecard_id`, `overall_score` |
| Edge cases | incomplete_scorecard passes through. |
| Expected synthetic result | 16.25 1, 37.5 1, 91.25 1 |
| Portability | Functions: IF, IFERROR, INDEX, MATCH (all in the portable set). Uses Excel Table structured references; recalculation verified in LibreOffice Calc 24.2, not yet in Excel itself. |

```text
=IF(tblReadinessSummary[[#This Row],[readiness_scorecard_id]]="","",IFERROR(INDEX(tblReadiness[overall_score],MATCH(tblReadinessSummary[[#This Row],[readiness_scorecard_id]],tblReadiness[readiness_scorecard_id],0)),"scorecard_not_found"))
```

#### `tblReadinessSummary[incomplete_required_evidence_flag]`

| Item | Value |
|---|---|
| Workbook tab | Readiness Scorecard |
| Table | `tblReadinessSummary` |
| Field | `incomplete_required_evidence_flag` (R3 field) |
| Authority | `reproduces_r1_rule` |
| Purpose | TRUE when required evidence is incomplete (R1). |
| R1 source rule or config | config/readiness-weights.yaml (calculation) |
| Input fields | `readiness_scorecard_id`, `incomplete_required_evidence_flag` |
| Edge cases | scorecard_not_found. |
| Expected synthetic result | TRUE 3, FALSE 0 |
| Portability | Functions: IF, IFERROR, INDEX, MATCH (all in the portable set). Uses Excel Table structured references; recalculation verified in LibreOffice Calc 24.2, not yet in Excel itself. |

```text
=IF(tblReadinessSummary[[#This Row],[readiness_scorecard_id]]="","",IFERROR(INDEX(tblReadiness[incomplete_required_evidence_flag],MATCH(tblReadinessSummary[[#This Row],[readiness_scorecard_id]],tblReadiness[readiness_scorecard_id],0)),"scorecard_not_found"))
```

#### `tblReadinessSummary[evidence_warning]`

| Item | Value |
|---|---|
| Workbook tab | Readiness Scorecard |
| Table | `tblReadinessSummary` |
| Field | `evidence_warning` (R3 field) |
| Authority | `r3_workbook_validation` |
| Purpose | Plain-language warning. It informs the human reviewer and never records a decision. |
| R1 source rule or config | None: R3 view over R1 records |
| Input fields | `readiness_scorecard_id`, `incomplete_required_evidence_flag` |
| Edge cases | scorecard_not_found. |
| Expected synthetic result | Required evidence incomplete: resolve before the human launch decision 3 |
| Portability | Functions: IF (all in the portable set). Uses Excel Table structured references; recalculation verified in LibreOffice Calc 24.2, not yet in Excel itself. |

```text
=IF(tblReadinessSummary[[#This Row],[readiness_scorecard_id]]="","",IF(tblReadinessSummary[[#This Row],[incomplete_required_evidence_flag]]=TRUE,"Required evidence incomplete: resolve before the human launch decision",IF(tblReadinessSummary[[#This Row],[incomplete_required_evidence_flag]]=FALSE,"Required evidence complete","scorecard_not_found")))
```

#### `tblReadinessSummary[event_evidence]`

| Item | Value |
|---|---|
| Workbook tab | Readiness Scorecard |
| Table | `tblReadinessSummary` |
| Field | `event_evidence` (R3 field) |
| Authority | `r3_workbook_validation` |
| Purpose | Reconciles the scorecard against the Event Log. |
| R1 source rule or config | None: R3 view over R1 records |
| Input fields | `readiness_scorecard_id`, `assessed_at`, `subject_id`, `event_type`, `event_reconciliation_from_at` |
| Edge cases | before_window for older scorecards. |
| Expected synthetic result | logged 3 |
| Portability | Functions: COUNTIFS, IF (all in the portable set). Uses Excel Table structured references; recalculation verified in LibreOffice Calc 24.2, not yet in Excel itself. |

```text
=IF(tblReadinessSummary[[#This Row],[readiness_scorecard_id]]="","",IF(tblReadinessSummary[[#This Row],[assessed_at]]<event_reconciliation_from_at,"before_window",IF(COUNTIFS(tblEventLog[subject_id],tblReadinessSummary[[#This Row],[readiness_scorecard_id]],tblEventLog[event_type],"readiness.scored")>0,"logged","missing:readiness.scored")))
```

### Capacity Inputs / `tblCapacityInputs`

#### `tblCapacityInputs[period]`

| Item | Value |
|---|---|
| Workbook tab | Capacity Inputs |
| Table | `tblCapacityInputs` |
| Field | `period` (R3 field) |
| Authority | `r3_workbook_validation` |
| Purpose | Month (YYYY-MM) of the component's planned due date, or of the phase entry for a phase summary. |
| R1 source rule or config | None: R3 view over R1 records |
| Input fields | `capacity_input_id`, `workload_component_id`, `planned_due_date`, `task_id`, `entered_at`, `phase_id` |
| Edge cases | Blank when the component is missing. |
| Expected synthetic result | 2026-09 15, 2026-10 14, 2026-08 2, 2026-05 1, 2026-06 1, 2026-07 2 |
| Portability | Functions: IF, IFERROR, INDEX, LEFT, MATCH (all in the portable set). Uses Excel Table structured references; recalculation verified in LibreOffice Calc 24.2, not yet in Excel itself. |

```text
=IF(tblCapacityInputs[[#This Row],[capacity_input_id]]="","",IFERROR(IF(LEFT(tblCapacityInputs[[#This Row],[workload_component_id]],3)="TSK",LEFT(INDEX(tblTasks[planned_due_date],MATCH(tblCapacityInputs[[#This Row],[workload_component_id]],tblTasks[task_id],0))&"",7),LEFT(INDEX(tblPhases[entered_at],MATCH(tblCapacityInputs[[#This Row],[workload_component_id]],tblPhases[phase_id],0))&"",7)),""))
```

#### `tblCapacityInputs[project_id]`

| Item | Value |
|---|---|
| Workbook tab | Capacity Inputs |
| Table | `tblCapacityInputs` |
| Field | `project_id` (R3 field) |
| Authority | `summarizes_r1_records` |
| Purpose | Project of the source record. |
| R1 source rule or config | None: R3 view over R1 records |
| Input fields | `capacity_input_id`, `source_entity_type`, `project_id`, `source_entity_id`, `task_id`, `request_id`, `handoff_id`, `phase_id` |
| Edge cases | source_not_found when the source record does not exist. |
| Expected synthetic result | PRJ-000001 6, PRJ-000002 12, PRJ-000003 17 |
| Portability | Functions: IF, IFERROR, INDEX, MATCH (all in the portable set). Uses Excel Table structured references; recalculation verified in LibreOffice Calc 24.2, not yet in Excel itself. |

```text
=IF(tblCapacityInputs[[#This Row],[capacity_input_id]]="","",IFERROR(IF(tblCapacityInputs[[#This Row],[source_entity_type]]="task",INDEX(tblTasks[project_id],MATCH(tblCapacityInputs[[#This Row],[source_entity_id]],tblTasks[task_id],0)),IF(tblCapacityInputs[[#This Row],[source_entity_type]]="request",INDEX(tblRequests[project_id],MATCH(tblCapacityInputs[[#This Row],[source_entity_id]],tblRequests[request_id],0)),IF(tblCapacityInputs[[#This Row],[source_entity_type]]="handoff",INDEX(tblHandoffs[project_id],MATCH(tblCapacityInputs[[#This Row],[source_entity_id]],tblHandoffs[handoff_id],0)),IF(tblCapacityInputs[[#This Row],[source_entity_type]]="phase",INDEX(tblPhases[project_id],MATCH(tblCapacityInputs[[#This Row],[source_entity_id]],tblPhases[phase_id],0)),"source_not_found"))))&"","source_not_found"))
```

#### `tblCapacityInputs[role_id]`

| Item | Value |
|---|---|
| Workbook tab | Capacity Inputs |
| Table | `tblCapacityInputs` |
| Field | `role_id` (R3 field) |
| Authority | `summarizes_r1_records` |
| Purpose | Role carrying the work: task or request owner, handoff receiving role, or phase owner. |
| R1 source rule or config | None: R3 view over R1 records |
| Input fields | `capacity_input_id`, `source_entity_type`, `owner_role_id`, `source_entity_id`, `task_id`, `request_id`, `to_role_id`, `handoff_id`, `phase_id` |
| Edge cases | source_not_found. |
| Expected synthetic result | ROL-000001 15, ROL-000004 14, ROL-000005 3, ROL-000006 3 |
| Portability | Functions: IF, IFERROR, INDEX, MATCH (all in the portable set). Uses Excel Table structured references; recalculation verified in LibreOffice Calc 24.2, not yet in Excel itself. |

```text
=IF(tblCapacityInputs[[#This Row],[capacity_input_id]]="","",IFERROR(IF(tblCapacityInputs[[#This Row],[source_entity_type]]="task",INDEX(tblTasks[owner_role_id],MATCH(tblCapacityInputs[[#This Row],[source_entity_id]],tblTasks[task_id],0)),IF(tblCapacityInputs[[#This Row],[source_entity_type]]="request",INDEX(tblRequests[owner_role_id],MATCH(tblCapacityInputs[[#This Row],[source_entity_id]],tblRequests[request_id],0)),IF(tblCapacityInputs[[#This Row],[source_entity_type]]="handoff",INDEX(tblHandoffs[to_role_id],MATCH(tblCapacityInputs[[#This Row],[source_entity_id]],tblHandoffs[handoff_id],0)),IF(tblCapacityInputs[[#This Row],[source_entity_type]]="phase",INDEX(tblPhases[owner_role_id],MATCH(tblCapacityInputs[[#This Row],[source_entity_id]],tblPhases[phase_id],0)),"source_not_found"))))&"","source_not_found"))
```

#### `tblCapacityInputs[planned_hours]`

| Item | Value |
|---|---|
| Workbook tab | Capacity Inputs |
| Table | `tblCapacityInputs` |
| Field | `planned_hours` (R3 field) |
| Authority | `summarizes_r1_records` |
| Purpose | Planned hours of the workload component (a task, or the sum of a phase's tasks). Copied from R1 task data; never estimated here. |
| R1 source rule or config | None: R3 view over R1 records |
| Input fields | `capacity_input_id`, `workload_component_id`, `planned_hours`, `task_id`, `phase_id` |
| Edge cases | component_not_found; a blank task value counts as 0. |
| Expected synthetic result | 35 values, total 332 |
| Portability | Functions: IF, IFERROR, INDEX, LEFT, MATCH, SUMIFS (all in the portable set). Uses Excel Table structured references; recalculation verified in LibreOffice Calc 24.2, not yet in Excel itself. |

```text
=IF(tblCapacityInputs[[#This Row],[capacity_input_id]]="","",IFERROR(IF(LEFT(tblCapacityInputs[[#This Row],[workload_component_id]],3)="TSK",INDEX(tblTasks[planned_hours],MATCH(tblCapacityInputs[[#This Row],[workload_component_id]],tblTasks[task_id],0))*1,IF(LEFT(tblCapacityInputs[[#This Row],[workload_component_id]],3)="PHS",SUMIFS(tblTasks[planned_hours],tblTasks[phase_id],tblCapacityInputs[[#This Row],[workload_component_id]]),"component_not_found")),"component_not_found"))
```

#### `tblCapacityInputs[actual_hours]`

| Item | Value |
|---|---|
| Workbook tab | Capacity Inputs |
| Table | `tblCapacityInputs` |
| Field | `actual_hours` (R3 field) |
| Authority | `summarizes_r1_records` |
| Purpose | Actual hours of the workload component. |
| R1 source rule or config | None: R3 view over R1 records |
| Input fields | `capacity_input_id`, `workload_component_id`, `actual_hours`, `task_id`, `phase_id` |
| Edge cases | Same as planned_hours. |
| Expected synthetic result | 35 values, total 257.5 |
| Portability | Functions: IF, IFERROR, INDEX, LEFT, MATCH, SUMIFS (all in the portable set). Uses Excel Table structured references; recalculation verified in LibreOffice Calc 24.2, not yet in Excel itself. |

```text
=IF(tblCapacityInputs[[#This Row],[capacity_input_id]]="","",IFERROR(IF(LEFT(tblCapacityInputs[[#This Row],[workload_component_id]],3)="TSK",INDEX(tblTasks[actual_hours],MATCH(tblCapacityInputs[[#This Row],[workload_component_id]],tblTasks[task_id],0))*1,IF(LEFT(tblCapacityInputs[[#This Row],[workload_component_id]],3)="PHS",SUMIFS(tblTasks[actual_hours],tblTasks[phase_id],tblCapacityInputs[[#This Row],[workload_component_id]]),"component_not_found")),"component_not_found"))
```

#### `tblCapacityInputs[org_stage]`

| Item | Value |
|---|---|
| Workbook tab | Capacity Inputs |
| Table | `tblCapacityInputs` |
| Field | `org_stage` (R3 field) |
| Authority | `summarizes_r1_records` |
| Purpose | Organization stage of the source project. |
| R1 source rule or config | None: R3 view over R1 records |
| Input fields | `capacity_input_id`, `org_stage`, `project_id` |
| Edge cases | Blank when the project is missing. |
| Expected synthetic result | startup 6, early_scale 12, structured_growth 17 |
| Portability | Functions: IF, IFERROR, INDEX, MATCH (all in the portable set). Uses Excel Table structured references; recalculation verified in LibreOffice Calc 24.2, not yet in Excel itself. |

```text
=IF(tblCapacityInputs[[#This Row],[capacity_input_id]]="","",IFERROR(INDEX(tblProjects[org_stage],MATCH(tblCapacityInputs[[#This Row],[project_id]],tblProjects[project_id],0))&"",""))
```

#### `tblCapacityInputs[export_ready_flag]`

| Item | Value |
|---|---|
| Workbook tab | Capacity Inputs |
| Table | `tblCapacityInputs` |
| Field | `export_ready_flag` (R3 field) |
| Authority | `r3_workbook_validation` |
| Purpose | TRUE when the row can be exported: no duplicate authoritative component, numeric hours, unit hours, known source and method. |
| R1 source rule or config | None: R3 view over R1 records |
| Input fields | `capacity_input_id`, `duplicate_authoritative_flag`, `planned_hours`, `actual_hours`, `unit`, `project_id`, `lookup_type`, `key`, `capacity_inclusion_method` |
| Edge cases | FALSE rows stay visible for correction. |
| Expected synthetic result | TRUE 35, FALSE 0 |
| Portability | Functions: AND, COUNTIFS, IF, ISNUMBER, NOT (all in the portable set). Uses Excel Table structured references; recalculation verified in LibreOffice Calc 24.2, not yet in Excel itself. |

```text
=IF(tblCapacityInputs[[#This Row],[capacity_input_id]]="","",AND(NOT(tblCapacityInputs[[#This Row],[duplicate_authoritative_flag]]),ISNUMBER(tblCapacityInputs[[#This Row],[planned_hours]]),ISNUMBER(tblCapacityInputs[[#This Row],[actual_hours]]),tblCapacityInputs[[#This Row],[unit]]="hours",tblCapacityInputs[[#This Row],[project_id]]<>"source_not_found",COUNTIFS(tblLookupEntries[lookup_type],"capacity_inclusion_method",tblLookupEntries[key],tblCapacityInputs[[#This Row],[capacity_inclusion_method]])>0))
```

#### `tblCapacityInputs[duplicate_authoritative_flag]`

| Item | Value |
|---|---|
| Workbook tab | Capacity Inputs |
| Table | `tblCapacityInputs` |
| Field | `duplicate_authoritative_flag` (R3 helper, not exported) |
| Authority | `r3_workbook_validation` |
| Purpose | TRUE when a workload component is authoritative in more than one row. Every such row is excluded from totals. |
| R1 source rule or config | None: R3 view over R1 records |
| Input fields | `capacity_input_id`, `capacity_inclusion_method`, `workload_component_id` |
| Edge cases | Both duplicate rows are flagged. |
| Expected synthetic result | TRUE 0, FALSE 35 |
| Portability | Functions: AND, COUNTIFS, IF (all in the portable set). Uses Excel Table structured references; recalculation verified in LibreOffice Calc 24.2, not yet in Excel itself. |

```text
=IF(tblCapacityInputs[[#This Row],[capacity_input_id]]="","",AND(tblCapacityInputs[[#This Row],[capacity_inclusion_method]]="authoritative_workload",COUNTIFS(tblCapacityInputs[workload_component_id],tblCapacityInputs[[#This Row],[workload_component_id]],tblCapacityInputs[capacity_inclusion_method],"authoritative_workload")>1))
```

#### `tblCapacityInputs[authoritative_planned_hours]`

| Item | Value |
|---|---|
| Workbook tab | Capacity Inputs |
| Table | `tblCapacityInputs` |
| Field | `authoritative_planned_hours` (R3 helper, not exported) |
| Authority | `r3_workbook_validation` |
| Purpose | Planned hours that count toward the authoritative total; 0 for informational, excluded, or duplicate rows. |
| R1 source rule or config | None: R3 view over R1 records |
| Input fields | `capacity_input_id`, `capacity_inclusion_method`, `duplicate_authoritative_flag`, `planned_hours` |
| Edge cases | Prevents double counting. |
| Expected synthetic result | 35 values, total 230 |
| Portability | Functions: AND, IF, ISNUMBER, NOT (all in the portable set). Uses Excel Table structured references; recalculation verified in LibreOffice Calc 24.2, not yet in Excel itself. |

```text
=IF(tblCapacityInputs[[#This Row],[capacity_input_id]]="","",IF(AND(tblCapacityInputs[[#This Row],[capacity_inclusion_method]]="authoritative_workload",NOT(tblCapacityInputs[[#This Row],[duplicate_authoritative_flag]]),ISNUMBER(tblCapacityInputs[[#This Row],[planned_hours]])),tblCapacityInputs[[#This Row],[planned_hours]],0))
```

#### `tblCapacityInputs[authoritative_actual_hours]`

| Item | Value |
|---|---|
| Workbook tab | Capacity Inputs |
| Table | `tblCapacityInputs` |
| Field | `authoritative_actual_hours` (R3 helper, not exported) |
| Authority | `r3_workbook_validation` |
| Purpose | Actual hours that count toward the authoritative total. |
| R1 source rule or config | None: R3 view over R1 records |
| Input fields | `capacity_input_id`, `capacity_inclusion_method`, `duplicate_authoritative_flag`, `actual_hours` |
| Edge cases | Same as authoritative_planned_hours. |
| Expected synthetic result | 35 values, total 197.5 |
| Portability | Functions: AND, IF, ISNUMBER, NOT (all in the portable set). Uses Excel Table structured references; recalculation verified in LibreOffice Calc 24.2, not yet in Excel itself. |

```text
=IF(tblCapacityInputs[[#This Row],[capacity_input_id]]="","",IF(AND(tblCapacityInputs[[#This Row],[capacity_inclusion_method]]="authoritative_workload",NOT(tblCapacityInputs[[#This Row],[duplicate_authoritative_flag]]),ISNUMBER(tblCapacityInputs[[#This Row],[actual_hours]])),tblCapacityInputs[[#This Row],[actual_hours]],0))
```

### Event Log / `tblEventLog`

#### `tblEventLog[event_type_check]`

| Item | Value |
|---|---|
| Workbook tab | Event Log |
| Table | `tblEventLog` |
| Field | `event_type_check` (R3 helper, not exported) |
| Authority | `reproduces_r1_rule` |
| Purpose | Checks the event type is an R1 v0.1 event and its subject type matches the R1 catalog. |
| R1 source rule or config | standard/event-catalog.yaml |
| Input fields | `event_id`, `lookup_type`, `key`, `event_type`, `display_value`, `subject_type` |
| Edge cases | not_registered_for_v0_1 or subject_type_mismatch. |
| Expected synthetic result | registered 38 |
| Portability | Functions: COUNTIFS, IF (all in the portable set). Uses Excel Table structured references; recalculation verified in LibreOffice Calc 24.2, not yet in Excel itself. |

```text
=IF(tblEventLog[[#This Row],[event_id]]="","",IF(COUNTIFS(tblLookupEntries[lookup_type],"event_type",tblLookupEntries[key],tblEventLog[[#This Row],[event_type]])=0,"not_registered_for_v0_1",IF(COUNTIFS(tblLookupEntries[lookup_type],"event_type",tblLookupEntries[key],tblEventLog[[#This Row],[event_type]],tblLookupEntries[display_value],tblEventLog[[#This Row],[subject_type]])=0,"subject_type_mismatch","registered")))
```

#### `tblEventLog[source_repo_check]`

| Item | Value |
|---|---|
| Workbook tab | Event Log |
| Table | `tblEventLog` |
| Field | `source_repo_check` (R3 helper, not exported) |
| Authority | `reproduces_r1_rule` |
| Purpose | Every v0.1 event is produced by R1; the workbook records R1 events and never produces its own. |
| R1 source rule or config | standard/event-catalog.yaml (producer_repo) |
| Input fields | `event_id`, `source_repo` |
| Edge cases | wrong_source_repo. |
| Expected synthetic result | catalog_producer 38 |
| Portability | Functions: IF (all in the portable set). Uses Excel Table structured references; recalculation verified in LibreOffice Calc 24.2, not yet in Excel itself. |

```text
=IF(tblEventLog[[#This Row],[event_id]]="","",IF(tblEventLog[[#This Row],[source_repo]]="implementation-operating-system","catalog_producer","wrong_source_repo"))
```

#### `tblEventLog[actor_check]`

| Item | Value |
|---|---|
| Workbook tab | Event Log |
| Table | `tblEventLog` |
| Field | `actor_check` (R3 helper, not exported) |
| Authority | `reproduces_r1_rule` |
| Purpose | Human actors are PER- people; system actors are configured R1 rules; no AI actor in v0.1. |
| R1 source rule or config | standard/schemas/event.schema.json (actor rules) |
| Input fields | `event_id`, `actor_type`, `actor_id`, `lookup_type`, `key` |
| Edge cases | One of four failure labels. |
| Expected synthetic result | valid 38 |
| Portability | Functions: COUNTIFS, IF, LEFT (all in the portable set). Uses Excel Table structured references; recalculation verified in LibreOffice Calc 24.2, not yet in Excel itself. |

```text
=IF(tblEventLog[[#This Row],[event_id]]="","",IF(tblEventLog[[#This Row],[actor_type]]="human",IF(LEFT(tblEventLog[[#This Row],[actor_id]],4)="PER-","valid","human_actor_not_person"),IF(tblEventLog[[#This Row],[actor_type]]="system",IF(COUNTIFS(tblLookupEntries[lookup_type],"rule_id",tblLookupEntries[key],tblEventLog[[#This Row],[actor_id]])>0,"valid","unknown_system_actor"),IF(tblEventLog[[#This Row],[actor_type]]="ai_agent","ai_actor_not_used_in_v0_1","invalid_actor_type"))))
```

#### `tblEventLog[subject_check]`

| Item | Value |
|---|---|
| Workbook tab | Event Log |
| Table | `tblEventLog` |
| Field | `subject_check` (R3 helper, not exported) |
| Authority | `r3_workbook_validation` |
| Purpose | Checks the event subject exists in the matching workbook table. |
| R1 source rule or config | None: R3 view over R1 records |
| Input fields | `event_id`, `subject_id`, `project_id`, `phase_id`, `milestone_id`, `task_id`, `request_id`, `risk_id`, `issue_id`, `readiness_scorecard_id`, `gate_assessment_id`, `handoff_id` |
| Edge cases | event_only_record for gate assessments and handoffs that R1 holds only as events. |
| Expected synthetic result | found 34, event_only_record 4 |
| Portability | Functions: COUNTIF, IF, LEFT (all in the portable set). Uses Excel Table structured references; recalculation verified in LibreOffice Calc 24.2, not yet in Excel itself. |

```text
=IF(tblEventLog[[#This Row],[event_id]]="","",IF(LEFT(tblEventLog[[#This Row],[subject_id]],3)="PRJ",IF(COUNTIF(tblProjects[project_id],tblEventLog[[#This Row],[subject_id]])>0,"found","missing"),IF(LEFT(tblEventLog[[#This Row],[subject_id]],3)="PHS",IF(COUNTIF(tblPhases[phase_id],tblEventLog[[#This Row],[subject_id]])>0,"found","missing"),IF(LEFT(tblEventLog[[#This Row],[subject_id]],3)="MLS",IF(COUNTIF(tblMilestones[milestone_id],tblEventLog[[#This Row],[subject_id]])>0,"found","missing"),IF(LEFT(tblEventLog[[#This Row],[subject_id]],3)="TSK",IF(COUNTIF(tblTasks[task_id],tblEventLog[[#This Row],[subject_id]])>0,"found","missing"),IF(LEFT(tblEventLog[[#This Row],[subject_id]],3)="REQ",IF(COUNTIF(tblRequests[request_id],tblEventLog[[#This Row],[subject_id]])>0,"found","missing"),IF(LEFT(tblEventLog[[#This Row],[subject_id]],3)="RSK",IF(COUNTIF(tblRisks[risk_id],tblEventLog[[#This Row],[subject_id]])>0,"found","missing"),IF(LEFT(tblEventLog[[#This Row],[subject_id]],3)="ISS",IF(COUNTIF(tblIssues[issue_id],tblEventLog[[#This Row],[subject_id]])>0,"found","missing"),IF(LEFT(tblEventLog[[#This Row],[subject_id]],3)="RDS",IF(COUNTIF(tblReadinessSummary[readiness_scorecard_id],tblEventLog[[#This Row],[subject_id]])>0,"found","missing"),IF(LEFT(tblEventLog[[#This Row],[subject_id]],3)="GAT",IF(COUNTIF(tblGateAssessments[gate_assessment_id],tblEventLog[[#This Row],[subject_id]])>0,"found","event_only_record"),IF(LEFT(tblEventLog[[#This Row],[subject_id]],3)="HND",IF(COUNTIF(tblHandoffs[handoff_id],tblEventLog[[#This Row],[subject_id]])>0,"found","event_only_record"),"unsupported_subject")))))))))))
```

#### `tblEventLog[payload_check]`

| Item | Value |
|---|---|
| Workbook tab | Event Log |
| Table | `tblEventLog` |
| Field | `payload_check` (R3 helper, not exported) |
| Authority | `r3_workbook_validation` |
| Purpose | Shape check that payload is a JSON object. Full JSON and schema validation runs in tools/validate.py. |
| R1 source rule or config | None: R3 view over R1 records |
| Input fields | `event_id`, `payload` |
| Edge cases | not_json_object. |
| Expected synthetic result | object_text 38 |
| Portability | Functions: AND, IF, LEFT, RIGHT, TRIM (all in the portable set). Uses Excel Table structured references; recalculation verified in LibreOffice Calc 24.2, not yet in Excel itself. |

```text
=IF(tblEventLog[[#This Row],[event_id]]="","",IF(AND(LEFT(TRIM(tblEventLog[[#This Row],[payload]]),1)="{",RIGHT(TRIM(tblEventLog[[#This Row],[payload]]),1)="}"),"object_text","not_json_object"))
```

#### `tblEventLog[request_transition_check]`

| Item | Value |
|---|---|
| Workbook tab | Event Log |
| Table | `tblEventLog` |
| Field | `request_transition_check` (R3 helper, not exported) |
| Authority | `reproduces_r1_rule` |
| Purpose | For request.status_changed, checks from_status > to_status is a legal R1 transition (config/request-state-machine.yaml). |
| R1 source rule or config | config/request-state-machine.yaml (transitions) |
| Input fields | `event_id`, `event_type`, `lookup_type`, `key`, `payload` |
| Edge cases | Reads the payload text written in the standard JSON form; illegal when the pair is missing. |
| Expected synthetic result | not_applicable 33, legal 5 |
| Portability | Functions: COUNTIFS, FIND, IF, IFERROR, MID (all in the portable set). Uses Excel Table structured references; recalculation verified in LibreOffice Calc 24.2, not yet in Excel itself. |

```text
=IF(tblEventLog[[#This Row],[event_id]]="","",IF(tblEventLog[[#This Row],[event_type]]<>"request.status_changed","not_applicable",IF(COUNTIFS(tblLookupEntries[lookup_type],"request_transition",tblLookupEntries[key],IFERROR(MID(tblEventLog[[#This Row],[payload]],FIND("""from_status"": """,tblEventLog[[#This Row],[payload]])+16,FIND("""",tblEventLog[[#This Row],[payload]],FIND("""from_status"": """,tblEventLog[[#This Row],[payload]])+16)-FIND("""from_status"": """,tblEventLog[[#This Row],[payload]])-16),"")&">"&IFERROR(MID(tblEventLog[[#This Row],[payload]],FIND("""to_status"": """,tblEventLog[[#This Row],[payload]])+14,FIND("""",tblEventLog[[#This Row],[payload]],FIND("""to_status"": """,tblEventLog[[#This Row],[payload]])+14)-FIND("""to_status"": """,tblEventLog[[#This Row],[payload]])-14),""))>0,"legal","illegal")))
```

### KPI Summary / `tblPhaseSummary`

#### `tblPhaseSummary[phase_key]`

| Item | Value |
|---|---|
| Workbook tab | KPI Summary |
| Table | `tblPhaseSummary` |
| Field | `phase_key` (R3 field) |
| Authority | `summarizes_r1_records` |
| Purpose | The lifecycle phase at this position (R1 order). |
| R1 source rule or config | None: R3 view over R1 records |
| Input fields | `position`, `lst_phase_key` |
| Edge cases | Blank past the last phase. |
| Expected synthetic result | initiate 1, discover 1, design 1, build 1, validate 1, enable 1, launch 1, stabilize 1, transition 1, review 1 |
| Portability | Functions: IFERROR, INDEX (all in the portable set). Uses Excel Table structured references; recalculation verified in LibreOffice Calc 24.2, not yet in Excel itself. |

```text
=IFERROR(INDEX(lst_phase_key,tblPhaseSummary[[#This Row],[position]]),"")
```

#### `tblPhaseSummary[project_count]`

| Item | Value |
|---|---|
| Workbook tab | KPI Summary |
| Table | `tblPhaseSummary` |
| Field | `project_count` (R3 field) |
| Authority | `summarizes_r1_records` |
| Purpose | Projects whose current phase is this phase. |
| R1 source rule or config | None: R3 view over R1 records |
| Input fields | `current_phase_key`, `phase_key` |
| Edge cases | 0 when none. |
| Expected synthetic result | 0 7, 1 3 |
| Portability | Functions: COUNTIF (all in the portable set). Uses Excel Table structured references; recalculation verified in LibreOffice Calc 24.2, not yet in Excel itself. |

```text
=COUNTIF(tblProjects[current_phase_key],tblPhaseSummary[[#This Row],[phase_key]])
```

### KPI Summary / `tblRequestStatusSummary`

#### `tblRequestStatusSummary[request_status]`

| Item | Value |
|---|---|
| Workbook tab | KPI Summary |
| Table | `tblRequestStatusSummary` |
| Field | `request_status` (R3 field) |
| Authority | `summarizes_r1_records` |
| Purpose | The R1 request status at this position. |
| R1 source rule or config | None: R3 view over R1 records |
| Input fields | `position`, `lst_request_status` |
| Edge cases | Blank past the last status. |
| Expected synthetic result | submitted 1, triaged 1, awaiting_approval 1, accepted 1, in_progress 1, blocked 1, ready_for_handoff 1, handed_off 1, closed 1 |
| Portability | Functions: IFERROR, INDEX (all in the portable set). Uses Excel Table structured references; recalculation verified in LibreOffice Calc 24.2, not yet in Excel itself. |

```text
=IFERROR(INDEX(lst_request_status,tblRequestStatusSummary[[#This Row],[position]]),"")
```

#### `tblRequestStatusSummary[request_count]`

| Item | Value |
|---|---|
| Workbook tab | KPI Summary |
| Table | `tblRequestStatusSummary` |
| Field | `request_count` (R3 field) |
| Authority | `summarizes_r1_records` |
| Purpose | Requests in this status. |
| R1 source rule or config | None: R3 view over R1 records |
| Input fields | `status`, `request_status` |
| Edge cases | 0 when none. |
| Expected synthetic result | 1 8, 0 1 |
| Portability | Functions: COUNTIF (all in the portable set). Uses Excel Table structured references; recalculation verified in LibreOffice Calc 24.2, not yet in Excel itself. |

```text
=COUNTIF(tblRequests[status],tblRequestStatusSummary[[#This Row],[request_status]])
```

### KPI Summary / `tblReadinessByProject`

#### `tblReadinessByProject[project_id]`

| Item | Value |
|---|---|
| Workbook tab | KPI Summary |
| Table | `tblReadinessByProject` |
| Field | `project_id` (R3 field) |
| Authority | `summarizes_r1_records` |
| Purpose | The project at this position on the Projects tab. |
| R1 source rule or config | None: R3 view over R1 records |
| Input fields | `project_id`, `position` |
| Edge cases | Blank past the last project. |
| Expected synthetic result | PRJ-000001 1, PRJ-000002 1, PRJ-000003 1, (blank) 7 |
| Portability | Functions: IFERROR, INDEX (all in the portable set). Uses Excel Table structured references; recalculation verified in LibreOffice Calc 24.2, not yet in Excel itself. |

```text
=IFERROR(INDEX(tblProjects[project_id],tblReadinessByProject[[#This Row],[position]])&"","")
```

#### `tblReadinessByProject[readiness_score]`

| Item | Value |
|---|---|
| Workbook tab | KPI Summary |
| Table | `tblReadinessByProject` |
| Field | `readiness_score` (R3 field) |
| Authority | `summarizes_r1_records` |
| Purpose | Overall score of the project's first listed scorecard. It informs human review only. |
| R1 source rule or config | None: R3 view over R1 records |
| Input fields | `project_id`, `overall_score` |
| Edge cases | no_assessment when the project has no scorecard. |
| Expected synthetic result | 16.25 1, 37.5 1, 91.25 1, (blank) 7 |
| Portability | Functions: IF, IFERROR, INDEX, MATCH (all in the portable set). Uses Excel Table structured references; recalculation verified in LibreOffice Calc 24.2, not yet in Excel itself. |

```text
=IF(tblReadinessByProject[[#This Row],[project_id]]="","",IFERROR(INDEX(tblReadinessSummary[overall_score],MATCH(tblReadinessByProject[[#This Row],[project_id]],tblReadinessSummary[project_id],0)),"no_assessment"))
```

#### `tblReadinessByProject[evidence_warning]`

| Item | Value |
|---|---|
| Workbook tab | KPI Summary |
| Table | `tblReadinessByProject` |
| Field | `evidence_warning` (R3 field) |
| Authority | `summarizes_r1_records` |
| Purpose | The scorecard's required-evidence warning. |
| R1 source rule or config | None: R3 view over R1 records |
| Input fields | `project_id`, `evidence_warning` |
| Edge cases | no_assessment. |
| Expected synthetic result | Required evidence incomplete: resolve before the human launch decision 3, (blank) 7 |
| Portability | Functions: IF, IFERROR, INDEX, MATCH (all in the portable set). Uses Excel Table structured references; recalculation verified in LibreOffice Calc 24.2, not yet in Excel itself. |

```text
=IF(tblReadinessByProject[[#This Row],[project_id]]="","",IFERROR(INDEX(tblReadinessSummary[evidence_warning],MATCH(tblReadinessByProject[[#This Row],[project_id]],tblReadinessSummary[project_id],0)),"no_assessment"))
```

### KPI Summary / `tblKpiSummary`

| KPI | Definition | Source table | Grain | Interpretation | Authority | Expected synthetic value |
|---|---|---|---|---|---|---|
| `project_count` | Projects | `tblProjects` | workbook | How many projects the workbook tracks. | `summarizes_r1_records` | 3 |
| `active_project_count` | Active projects | `tblProjects` | workbook | Projects in delivery now. | `summarizes_r1_records` | 3 |
| `open_task_count` | Open tasks (not completed or cancelled) | `tblTasks` | workbook | Work not yet finished, including blocked and not started tasks. | `summarizes_r1_records` | 11 |
| `blocked_task_count` | Blocked tasks | `tblTasks` | workbook | Tasks waiting on something outside the task; look for the matching request or issue. | `summarizes_r1_records` | 1 |
| `overdue_task_count` | Overdue tasks as of calculation_as_of_at | `tblTasks` | workbook | Open tasks past their planned due date as of calculation_as_of_at; re-plan or escalate. | `r3_workbook_validation` | 2 |
| `open_risk_count` | Open risks (open or mitigating) | `tblRisks` | workbook | Risks still being worked; accepted and closed risks are excluded. | `summarizes_r1_records` | 4 |
| `open_issue_count` | Open issues (open or in progress) | `tblIssues` | workbook | Problems affecting delivery now. | `summarizes_r1_records` | 2 |
| `request_count` | Requests | `tblRequests` | workbook | All requests in the workbook. | `summarizes_r1_records` | 8 |
| `escalation_due_request_count` | Requests whose escalation time has passed | `tblRequests` | workbook | Requests whose R1 escalation time has passed; the escalation role should already be involved. | `r3_workbook_validation` | 1 |
| `readiness_scorecard_count` | Readiness scorecards | `tblReadinessSummary` | workbook | Scorecards recorded, including early pre-assessments. | `summarizes_r1_records` | 3 |
| `incomplete_readiness_evidence_count` | Scorecards with incomplete required evidence | `tblReadinessSummary` | workbook | Scorecards with missing required evidence; a person resolves these before any launch decision. | `summarizes_r1_records` | 3 |
| `event_log_row_count` | Event Log rows | `tblEventLog` | workbook | Rows in the Event Log. | `summarizes_r1_records` | 38 |
| `event_log_problem_count` | Event Log rows failing a check | `tblEventLog` | workbook | Event rows that fail a check; must be 0 before an Event Log export is trusted. | `r3_workbook_validation` | 0 |
| `missing_event_evidence_count` | Material changes inside the window with no Event Log row | `all record tables` | workbook | Material changes inside the reconciliation window that still need an Event Log row. | `r3_workbook_validation` | 27 |
| `reference_problem_count` | Records with an unresolved reference | `all record tables` | workbook | Records whose project, phase, or milestone reference does not resolve; must be 0. | `r3_workbook_validation` | 0 |

KPI formulas:

- `project_count`

  ```text
  =COUNTIF(tblProjects[project_id],"?*")
  ```

- `active_project_count`

  ```text
  =COUNTIF(tblProjects[project_status],"active")
  ```

- `open_task_count`

  ```text
  =COUNTIFS(tblTasks[task_id],"?*",tblTasks[status],"<>completed",tblTasks[status],"<>cancelled")
  ```

- `blocked_task_count`

  ```text
  =COUNTIF(tblTasks[status],"blocked")
  ```

- `overdue_task_count`

  ```text
  =COUNTIF(tblTasks[due_state],"overdue")
  ```

- `open_risk_count`

  ```text
  =COUNTIF(tblRisks[status],"open")+COUNTIF(tblRisks[status],"mitigating")
  ```

- `open_issue_count`

  ```text
  =COUNTIF(tblIssues[status],"open")+COUNTIF(tblIssues[status],"in_progress")
  ```

- `request_count`

  ```text
  =COUNTIF(tblRequests[request_id],"?*")
  ```

- `escalation_due_request_count`

  ```text
  =COUNTIF(tblRequests[escalation_due_state],"escalation_due")
  ```

- `readiness_scorecard_count`

  ```text
  =COUNTIF(tblReadinessSummary[readiness_scorecard_id],"?*")
  ```

- `incomplete_readiness_evidence_count`

  ```text
  =COUNTIF(tblReadinessSummary[incomplete_required_evidence_flag],TRUE)
  ```

- `event_log_row_count`

  ```text
  =COUNTIF(tblEventLog[event_id],"?*")
  ```

- `event_log_problem_count`

  ```text
  =COUNTIFS(tblEventLog[event_id],"?*",tblEventLog[event_type_check],"<>registered")+COUNTIFS(tblEventLog[event_id],"?*",tblEventLog[actor_check],"<>valid")+COUNTIF(tblEventLog[subject_check],"missing")+COUNTIF(tblEventLog[source_repo_check],"wrong_source_repo")+COUNTIF(tblEventLog[request_transition_check],"illegal")
  ```

- `missing_event_evidence_count`

  ```text
  =COUNTIF(tblProjects[event_evidence],"missing*")+COUNTIF(tblPhases[event_evidence],"missing*")+COUNTIF(tblMilestones[event_evidence],"missing*")+COUNTIF(tblGateAssessments[event_evidence],"missing*")+COUNTIF(tblTasks[event_evidence],"missing*")+COUNTIF(tblRequests[event_evidence],"missing*")+COUNTIF(tblHandoffs[event_evidence],"missing*")+COUNTIF(tblRisks[event_evidence],"missing*")+COUNTIF(tblIssues[event_evidence],"missing*")+COUNTIF(tblReadinessSummary[event_evidence],"missing*")
  ```

- `reference_problem_count`

  ```text
  =COUNTIFS(tblProjects[project_id],"?*",tblProjects[reference_check],"<>valid")+COUNTIFS(tblPhases[phase_id],"?*",tblPhases[reference_check],"<>valid")+COUNTIFS(tblMilestones[milestone_id],"?*",tblMilestones[reference_check],"<>valid")+COUNTIFS(tblGateAssessments[gate_assessment_id],"?*",tblGateAssessments[reference_check],"<>valid")+COUNTIFS(tblTasks[task_id],"?*",tblTasks[reference_check],"<>valid")+COUNTIFS(tblRequests[request_id],"?*",tblRequests[reference_check],"<>valid")+COUNTIFS(tblHandoffs[handoff_id],"?*",tblHandoffs[reference_check],"<>valid")+COUNTIFS(tblRisks[risk_id],"?*",tblRisks[reference_check],"<>valid")+COUNTIFS(tblIssues[issue_id],"?*",tblIssues[reference_check],"<>valid")
  ```

### Capacity Inputs / `tblCapacitySummary`

| Check | Meaning | Expected synthetic value |
|---|---|---|
| `authoritative_planned_hours_total` | Planned hours counted once, from authoritative rows only. | 230 |
| `authoritative_actual_hours_total` | Actual hours counted once, from authoritative rows only. | 197.5 |
| `task_planned_hours_total` | Planned hours on the Tasks tab, for reconciliation. | 230 |
| `task_actual_hours_total` | Actual hours on the Tasks tab, for reconciliation. | 197.5 |
| `hours_reconciliation` | reconciled when authoritative totals equal the task totals: every task counted exactly once. | reconciled |
| `authoritative_row_count` | Rows that carry authoritative workload. | 30 |
| `informational_row_count` | Rows exported for context; ignored by capacity math. | 2 |
| `excluded_row_count` | Rows that repeat a task's work and are excluded. | 3 |
| `duplicate_authoritative_count` | Rows claiming an already-authoritative component; must be 0. | 0 |
| `tasks_without_authoritative_row` | Tasks with no authoritative capacity row; must be 0 before export. | 0 |
| `export_ready_row_count` | Rows ready to export. | 35 |

Capacity check formulas:

- `authoritative_planned_hours_total`

  ```text
  =SUM(tblCapacityInputs[authoritative_planned_hours])
  ```

- `authoritative_actual_hours_total`

  ```text
  =SUM(tblCapacityInputs[authoritative_actual_hours])
  ```

- `task_planned_hours_total`

  ```text
  =SUM(tblTasks[planned_hours])
  ```

- `task_actual_hours_total`

  ```text
  =SUM(tblTasks[actual_hours])
  ```

- `hours_reconciliation`

  ```text
  =IF(AND(ABS(SUM(tblCapacityInputs[authoritative_planned_hours])-SUM(tblTasks[planned_hours]))<0.0001,ABS(SUM(tblCapacityInputs[authoritative_actual_hours])-SUM(tblTasks[actual_hours]))<0.0001),"reconciled","mismatch")
  ```

- `authoritative_row_count`

  ```text
  =COUNTIF(tblCapacityInputs[capacity_inclusion_method],"authoritative_workload")
  ```

- `informational_row_count`

  ```text
  =COUNTIF(tblCapacityInputs[capacity_inclusion_method],"informational_only")
  ```

- `excluded_row_count`

  ```text
  =COUNTIF(tblCapacityInputs[capacity_inclusion_method],"excluded_to_prevent_double_count")
  ```

- `duplicate_authoritative_count`

  ```text
  =COUNTIF(tblCapacityInputs[duplicate_authoritative_flag],TRUE)
  ```

- `tasks_without_authoritative_row`

  ```text
  =SUMPRODUCT((tblTasks[task_id]<>"")*(COUNTIFS(tblCapacityInputs[workload_component_id],tblTasks[task_id],tblCapacityInputs[capacity_inclusion_method],"authoritative_workload")=0))
  ```

- `export_ready_row_count`

  ```text
  =COUNTIF(tblCapacityInputs[export_ready_flag],TRUE)
  ```
