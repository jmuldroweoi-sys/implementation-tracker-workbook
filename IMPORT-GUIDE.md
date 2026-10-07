# Import guide

How to start using the workbook with your own projects instead of the bundled synthetic data, without breaking formulas or IDs. Two routes are supported: the builder route (recommended, reproducible) and the in-workbook route.

## Before you start

- Keep the original. Work on a copy and keep `workbook/implementation-tracker-workbook.xlsx` unchanged so you can always compare.
- Know the colors. Dark blue headers mark columns you edit. Grey headers and grey cells are formulas: never clear or type over them. Green headers mark read-only mirrors of R1.
- Never delete a formula column, rename a header, or reorder columns. Column names are R1 field names; exports and checks depend on them.

## Route A: build a workbook from your own files (recommended)

1. **Copy the workbook repository** (or just its `tools/`, `schemas/`, `config/`, and `standard/` folders) to a private location.
2. **Prepare your records as CSV files** in a folder, one file per R1 entity, using the exact R1 column headers: `projects.csv`, `phases.csv`, `milestones.csv`, `tasks.csv`, `requests.csv`, `risks.csv`, `issues.csv`, `readiness.csv`, and `events.jsonl`. Optional: `gate-assessments.csv` and `handoffs.csv` (columns as in `exports/csv/`). The bundled files in `data/synthetic/r1/` show the format.
3. **Preserve IDs.** Use `TYPE-NNNNNN` IDs with the registered prefixes (`PRJ-`, `PHS-`, `TSK-`, and so on) and never reuse an ID for a different record. Put your customer system's own reference in `customer_reference` (free text such as `CUST-1042`, never an R1-style ID) and a display name in `customer_label`.
4. **Prepare capacity-input rows** in a CSV like `data/synthetic/r3/capacity-inputs.csv`: one `authoritative_workload` row per task, plus any `informational_only` or `excluded_to_prevent_double_count` rows.
5. **Build:**

   ```bash
   python tools/build_workbook.py --data-dir PATH/TO/YOUR/FOLDER --capacity PATH/TO/capacity-inputs.csv --output PATH/TO/your-tracker.xlsx
   ```

6. **Select the organization stage and set the calculation timestamp** in the README tab (see below).
7. **Validate** (see below), then **export** (see below).

Your folder stays outside this repository. Never commit real records here.

## Route B: replace the synthetic rows inside the workbook

1. **Copy the workbook file** and open the copy.
2. **Clear synthetic rows safely.** On each record tab, for each table:
   - Delete table rows (select whole rows inside the table, then delete table rows) until one row remains. Do not delete the header or the last row: an Excel Table needs at least one data row to keep its formulas.
   - In the remaining row, clear only the white (input) cells. The grey cells show blank once the row's ID is empty; that is expected.
   - Clear the Event Log, Capacity Inputs, and Readiness rows the same way.
   - Leave README, Lookups, Escalation Rules, and KPI Summary alone.
3. **Enter your own projects.** Type into the white cells, or paste values column by column (Paste Values only, so you never paste over formulas). Type the next record directly under the last row: the table grows and the grey formula cells fill in automatically.
4. **Preserve IDs.** Keep each record's ID stable for its whole life. Never renumber.
5. **Preserve formulas.** If a grey cell was overwritten by mistake, copy the formula from the cell above it in the same column.
6. **Select the organization stage.** On the README tab, choose `selected_org_stage` (startup, early_scale, structured_growth, mature) and `operating_mode` (starter or full). The stage sets which fields and controls `config/stage-requirements.yaml` treats as required; it never changes the model.
7. **Set the calculation timestamp.** Set `calculation_as_of_at` to the moment you want due states and escalation states evaluated, in ISO 8601 UTC with a trailing `Z`, for example `2026-11-02T17:00:00Z`. Set `event_reconciliation_from_at` to the time from which every material change should have an Event Log row. Both are user-configurable parameters. No formula reads the clock, so these values decide every time-based result.
8. **Validate.** Scan every grey check column: `reference_check` should be `valid`, `event_evidence` should not start with `missing`, and the KPI rows `reference_problem_count` and `event_log_problem_count` should be 0. To run the full checks, export your rows as CSV (step 9) and use Route A to rebuild, then run the commands below.
9. **Export.** Save each table as CSV using exactly the columns listed for it in `config/export-map.yaml`, in that order. Never include grey helper columns in an export.

## Dates and IDs in the grid

- Enter dates as text `YYYY-MM-DD` and timestamps as text `YYYY-MM-DDTHH:MM:SSZ`. The date columns are formatted as text so the spreadsheet keeps them exactly.
- Drop-down lists come from R1. Status, phase, outcome, severity, and category lists reject other values. Role and profile lists only warn, so you can use your own `ROL-` and `PRF-` IDs.

## Validate and export commands

```bash
python tools/validate.py --root .
python tools/verify_workbook.py --require-recalc
python tools/build_workbook.py --exports
```

`--exports` recalculates a copy with LibreOffice and writes `exports/csv/*.csv` and `exports/jsonl/Event-Log.jsonl` from the workbook tables.
