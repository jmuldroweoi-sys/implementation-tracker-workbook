# Portfolio integration

The workbook (R3) is one of six connected repositories. It implements R1 and feeds later repositories through exports. None of the downstream repositories is built yet; this page records the contract they will use.

```text
R1 implementation-operating-system   (authority: model, rules, events)
        |  pinned copies (schemas/r1, data/synthetic/r1)
        v
R3 implementation-tracker-workbook    (applies R1 day to day)
        |  exports/csv/*.csv, exports/jsonl/Event-Log.jsonl
        +--> R2 capacity planning     (Capacity Inputs, tasks, requests, events)
        +--> R6 AI assistance         (reads exports, drafts proposals only)
        +--> analytics                (event and record exports)
R4 enablement   -> R3 v0.2 tabs (curriculum, training completion), not in v0.1
R5 team mgmt.   -> may read R3 exports as context only
```

## R1: the source of truth

R3 implements R1 and never reinterprets it. Every list, weight, band, scale, timer, and event definition comes from a pinned R1 commit (`standard/standard-reference.yaml`). When R1 changes, R3 re-syncs with `tools/sync_r1_contracts.py`, rebuilds, and must pass every check again before the new pin is used. R1 entity exports from the workbook use R1's own CSV contracts, so R1 tooling can read them unchanged.

## R2: capacity planning

R2 (`implementation-capacity-and-org-design`) will read:

- `exports/csv/capacity-inputs.csv`: workload rows with `capacity_inclusion_method`. R2 counts only `authoritative_workload` rows; `informational_only` rows are context; `excluded_to_prevent_double_count` rows repeat a task's work and must never be counted.
- `exports/csv/tasks.csv`, `requests.csv`, `phases.csv`, and the Event Log, for workload context.

R3 never calculates capacity, utilization, staffing need, hiring timing, or a capacity gap. Those belong to R2.

## R4: enablement

R4 (`implementation-enablement-program`) owns curriculum, training completion, and proficiency. R3 v0.1 has no R4 tabs, because R4 does not exist yet. R3 v0.2 adds R4-owned tabs after R4 v0.1 is built. Until then, training readiness is entered as criteria counts on the Readiness Scorecard tab.

## R5: team management

R5 (`implementation-team-management-toolkit`) may use workbook exports as context. Nothing in the workbook rates or ranks people, and R5 never changes workbook records.

## R6: AI assistance

R6 (`implementation-ai-agent-framework`) may read exports and draft proposals, such as a weekly status note. A proposal changes nothing until a named person approves it, and any approved change is made by a person in the workbook (or R1). No workbook calculation uses AI.

## Analytics

An analytics track may read `exports/jsonl/Event-Log.jsonl` and the CSV exports to practice reporting on the shared event contract. Every chart or table built from them carries the synthetic data label.
