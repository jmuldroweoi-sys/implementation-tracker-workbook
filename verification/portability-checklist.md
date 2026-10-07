# Portability checklist

What was actually tested, and what remains a documented limitation. Nothing here claims universal compatibility.

| Item | Status | Evidence |
|---|---|---|
| Macro-free | Tested | Verifier W05 and validator R35: no VBA project part, not a macro-enabled content type; a negative test injects a VBA part and the check fails |
| External-link free | Tested | Verifier W06 and validator R34: no external-link parts, no external relationship targets, no file references or URLs in formulas; a negative test injects a link and the check fails |
| Portable formulas | Tested (scan) | Verifier W07: only long-standing functions; no dynamic arrays, `LET`, `LAMBDA`, `XLOOKUP`, `OFFSET`, `INDIRECT`, `TODAY`, or `NOW` |
| Headless recalculation | Tested | LibreOffice Calc 24.2 recalculates every formula with 0 error values and results equal to the reference evaluator (verifier W12 and W13, `tests/test_formulas.py`); CI repeats this on every push |
| Structured references | Tested in LibreOffice | Excel Table references, including the stored this-row form `tblName[[#This Row],[column]]`, evaluate correctly in LibreOffice Calc 24.2 |
| ISO date handling | Tested | Dates and timestamps are stored as ISO 8601 text and compared as text; `DATEVALUE` and `TIMEVALUE` parse ISO text in LibreOffice for the escalation check |
| CSV export | Tested | Exports are regenerated from the recalculated workbook and are byte-identical to the committed files (W15); the eight R1 entity CSVs are byte-identical to the pinned R1 files (R25) |
| JSONL export | Tested | `Event-Log.jsonl` validates against the shared event schema (R24), equals the CSV export (R26), and is byte-identical to the pinned R1 events file |
| Reproducible file | Tested | A rebuild from pinned inputs is byte-identical (W11); the package is written uncompressed with fixed timestamps so the bytes do not depend on the machine |
| Excel compatibility | Not tested in this build | The workbook is an Office Open XML file with standard Excel Tables, defined names, list validation, conditional formatting, and one bar chart, written by openpyxl 3.1.5. It was not opened or recalculated in Excel during this build. The workbook asks the application to recalculate on open (`fullCalcOnLoad`). |
| Other spreadsheet applications | Not tested | Applications other than LibreOffice Calc 24.2 were not tested. Some do not support Excel Table structured references; in those, formulas would need plain ranges. |
| Locale | Limitation | `DATEVALUE` on ISO text is expected to work in ISO-aware locales; locales that reject ISO dates would make `escalation_due_check` show an error. Text comparisons of ISO values are locale-independent. |
| Protection | Limitation | Sheet protection on README, Lookups, Escalation Rules, and KPI Summary has no password; it prevents accidents, not tampering. |
| Adding rows | Expected, not tested in Excel | Tables declare calculated-column formulas so a new row typed under a table should fill its formulas in Excel; this was not exercised interactively in this build. |
