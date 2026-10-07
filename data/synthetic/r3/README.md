# R3 synthetic inputs

`capacity-inputs.csv` is synthetic data and an illustrative example: 35 capacity-input definitions for the R1 synthetic projects.

| Rows | Source | Method | Why |
|---|---|---|---|
| `CPI-000001` to `CPI-000030` | One per R1 task | `authoritative_workload` | A task's own effort is counted once |
| `CPI-000031`, `CPI-000032` | Requests `REQ-000002` and `REQ-000006` | `excluded_to_prevent_double_count` | Their work is already counted through tasks `TSK-000011` and `TSK-000026` |
| `CPI-000033` | Handoff `HND-000002` | `excluded_to_prevent_double_count` | Its work is already counted through task `TSK-000026` |
| `CPI-000034`, `CPI-000035` | Phases `PHS-000006` and `PHS-000015` | `informational_only` | Phase summaries repeat their tasks' hours, so they are context only |

The links between these requests or handoffs and those tasks are illustrative choices made for this R3 data set; R1 does not record them. The file holds only identifying and classification columns: hours, period, project, role, and organization stage are looked up by workbook formulas from the R1 records.
