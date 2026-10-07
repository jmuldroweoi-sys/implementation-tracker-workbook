# Starter Mode

Starter Mode is how one implementation professional runs the workbook in under one hour per week. That time budget is a design target, a proposed design value, not a measured result. Starter Mode does not use a smaller workbook: it is the same 12 tabs, the same IDs, and the same R1 rules. It only reduces what you update.

To turn it on, set `operating_mode` to `starter` on the README tab, and choose your `selected_org_stage` (usually `startup`).

## The weekly hour

| Order | Tab | What to do | Design-target minutes |
|---|---|---|---|
| 1 | README | Set `calculation_as_of_at` to now (ISO 8601 UTC) | 1 |
| 2 | Projects | Confirm each project's `project_status`, `current_phase_id`, and `target_launch_date` | 5 |
| 3 | Tasks | Update `status`, `actual_hours`, and `completed_at`; add next week's tasks; read `due_state` | 20 |
| 4 | Risks and Issues | Re-rate changed risks (likelihood, impact), log new issues, resolve fixed ones | 10 |
| 5 | Requests and Handoffs | Move requests along legal transitions; act on any `escalation_due`; record accepted handoffs | 10 |
| 6 | Readiness Scorecard | Only when a launch is within a few weeks: update criteria counts and evidence flags | 0 to 5 |
| 7 | Event Log | Add rows only for material changes (see below) | 5 |
| 8 | KPI Summary | Read the counts and the phase chart; note what needs attention | 3 |

Minutes are a proposed design value, not a measured result; they assume a handful of active projects.

## Material changes worth an Event Log row

In Starter Mode, add an event row only when one of these happens: a project is created or changes status, a phase is entered or exited, a gate outcome is recorded, a milestone is achieved or missed, a request is submitted, a risk or issue is logged, an issue is resolved, a handoff is accepted, or a readiness scorecard is completed. `config/event-mappings.yaml` lists the event type and payload for each. Task status changes are optional at the startup stage (see `config/stage-requirements.yaml`).

## What you can skip in Starter Mode

- Capacity Inputs (optional at startup and early-scale stages).
- Full event reconciliation (optional at startup): missing-evidence flags are reminders, not errors.
- Optional fields: hours, milestone links, and predecessors are optional at the startup stage.

## What you never skip

- Gate outcomes. When a gate happens, record it in `tblGateAssessments` with your name (`PER-` ID). A lightweight self-assessment is fine at the startup stage; a missing record is not.
- The `reference_check` columns. A value other than `valid` means a broken link between records.

## Moving to Full Mode

When a second person joins, or projects overlap, set `operating_mode` to `full` and follow [workbook-guide.md](workbook-guide.md). Nothing needs to be migrated.
