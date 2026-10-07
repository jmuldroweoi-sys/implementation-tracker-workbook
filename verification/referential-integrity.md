# Referential integrity

How the workbook keeps references between records whole, and the result on the bundled synthetic data. Result: **0 orphan references.**

| Reference | Where it is checked | Result on synthetic data |
|---|---|---|
| Project current phase belongs to the project; three profile IDs exist | `tblProjects[reference_check]` | 3 valid |
| Phase, milestone, gate assessment, task, request, handoff, risk, and issue project references | each table's `reference_check` | all valid |
| Phase, milestone, task, risk, and issue phase references in the same project | `reference_check` | all valid |
| Task milestone in the same project | `tblTasks[reference_check]` | 30 valid |
| Task predecessors exist | `tblTasks[predecessor_reference_valid]` | 0 invalid |
| Gate belongs to the phase | `tblPhases[gate_check]`, `tblGateAssessments[reference_check]` | all valid |
| Event subjects exist | `tblEventLog[subject_check]` | 34 found; 4 `event_only_record` (`HND-000001`, `GAT-000001`, `GAT-000003`, `GAT-000004`, which R1 holds only as events) |
| Capacity input sources and components exist | `tblCapacityInputs[project_id]`, `[planned_hours]` | 35 resolved |
| All references, through R1's own rule | validator R16 (calls pinned `r1_rules.reference_problems`) | 0 problems |
| ID format and registered prefixes | validator R15 | 938 ID values valid |

The KPI row `reference_problem_count` shows 0. Tests prove detection: an orphan task milestone fails validator check R16 (`tests/test_validate.py`).
