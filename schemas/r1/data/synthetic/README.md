# Synthetic data

All files in this folder are synthetic data generated for illustration. No company, customer, person, or project is represented. The scenarios exist only to demonstrate that the R1 model, rules, and validator work end to end. No value here represents historical performance, a measured result, or a benchmark.

The data set shows three projects as of 2026-10-05. Every derived value (risk scores, readiness scores, escalation times) was produced by `tools/r1_rules.py`, and `tools/validate.py` recomputes each one.

## Files

| File | Rows | Schema | Contents |
|---|---|---|---|
| `projects.csv` | 3 | `schemas/project.schema.json` | Synthetic Projects A, B, and C |
| `phases.csv` | 15 | `schemas/phase.schema.json` | Phase instances: A 2, B 4, C 9 |
| `milestones.csv` | 12 | `schemas/milestone.schema.json` | A 2, B 4, C 6 |
| `tasks.csv` | 30 | `schemas/task.schema.json` | A 6, B 10, C 14, with predecessors, critical flags, and hours |
| `requests.csv` | 8 | `schemas/request.schema.json` | A 1, B 3, C 4, across eight request statuses |
| `risks.csv` | 6 | `schemas/risk.schema.json` | A 1, B 3, C 2 |
| `issues.csv` | 5 | `schemas/issue.schema.json` | B 2, C 3 |
| `readiness.csv` | 18 | `schemas/readiness-scorecard.schema.json` | 3 scorecards x 6 canonical categories |
| `events.jsonl` | 38 | `standard/schemas/event.schema.json` | A deterministic sample of events matching the records |

CSV conventions follow `standard/field-conventions.md`: an empty cell means not applicable or not yet known, arrays are separated by semicolons with no spaces, timestamps are UTC ending in `Z`, and every record carries `schema_version` 0.1.0.

## Scenarios

| Scenario | Project | Stage | What it tests |
|---|---|---|---|
| Scenario A | Synthetic Project A (`PRJ-000001`), Synthetic Organization A | startup | A simple implementation run by one person holding every internal role: intake handoff, a lightweight initiate gate, a moderate risk, a request in progress, and one lead-time flag (`TSK-000006` is planned to start before its predecessor `TSK-000005` is due). This is the project that `docs/practical-workflow.md` follows. |
| Scenario B | Synthetic Project B (`PRJ-000002`), Synthetic Organization B | early_scale | A design gate passed with a condition tracked as a risk, a high risk being mitigated, a blocked request escalated by `RUL-000003` exactly 48 hours after it was blocked, a blocked task, a request waiting for approval, an open sev2 issue, and a missed milestone. |
| Scenario C | Synthetic Project C (`PRJ-000003`), Synthetic Organization C | structured_growth | A rework loop (validate, build, validate), formal gates, a request handed off and accepted by a named support owner, and a launch-review readiness scorecard of 91.25 with incomplete required evidence. The launch gate is still `awaiting_gate`: the data never records a launch decision. |

## Readiness rows

`readiness.csv` holds one row per category for each of three scorecards. Rows repeat their scorecard's fields (ID, project, purpose, time, overall score, incomplete-evidence flag).

- `RDS-000001` (Project A) and `RDS-000002` (Project B) are `pre_assessment` scorecards: early checks that show gaps. They feed no gate and are not launch results.
- `RDS-000003` (Project C) is the `launch_review` scorecard that the launch gate reviewer will see. It informs that review; a named human still records the launch decision.

## Roles and people

Records assign work to roles. People appear only as `PER-` IDs with neutral labels, never names.

| Role ID | Role key (`lifecycle/lifecycle.yaml`) |
|---|---|
| `ROL-000001` | implementation_lead |
| `ROL-000002` | customer_sponsor |
| `ROL-000003` | delivery_leadership |
| `ROL-000004` | technical_specialist |
| `ROL-000005` | enablement_lead |
| `ROL-000006` | support_owner |
| `ROL-000007` | customer_contact |
| `ROL-000008` | commercial_owner |

| Person ID | Label | Roles held in the scenarios |
|---|---|---|
| `PER-000001` | Person A | Scenario A: implementation lead, technical specialist, enablement lead, and support owner (solo mode) |
| `PER-000002` | Person B | Scenario B: implementation lead |
| `PER-000003` | Person C | Scenario C: implementation lead |
| `PER-000004` | Person D | Scenario C: delivery leadership, the launch gate approver (no decision recorded yet) |
| `PER-000005` | Person E | Scenario C: support owner |

Profiles referenced by the projects (`PRF-000001` to `PRF-000004`) are the illustrative example profiles in `profiles/examples/`.

## Events

`events.jsonl` is a deterministic sample of 38 events that demonstrates all 16 R1 core event types used in version 0.1. It is not a complete audit log: records that changed before the sample window, or outside the sample, have no event here. Every event in the file is consistent with the records: its subject exists, its payload matches the record, status events chain in order and end at the record's current status, request moves follow `config/request-state-machine.yaml`, and the escalation fires at the request's `escalation_due_at`.

Gate assessments (`GAT-`) and handoffs (`HND-`) have no CSV in version 0.1. They appear through their `gate.assessed` and `handoff.completed` events, and their full record shape is shown by the examples in their schemas.

No event uses an AI actor, and no event belongs to a scenario pack.
