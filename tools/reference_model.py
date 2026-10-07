"""Deterministic reference evaluator for the workbook.

Computes, in Python, the value every workbook formula must produce, from the same pinned
R1 inputs the builder writes. R1 calculations use R1's own pinned rule module, and every
formula column uses the `py` twin declared next to its spreadsheet formula in
tools/workbook_spec.py.

The reference evaluator is not the workbook. It is the independent expectation that the
recalculated workbook (tools/verify_workbook.py) and the expected values
(verification/expected-values.yaml) are checked against.
"""

from __future__ import annotations

from pathlib import Path

import workbook_spec as W

SETTING_ROWS = (
    ("workbook_id", False, "Workbook ID (WBK). Keep it when you copy the workbook for a new team."),
    ("workbook_version", False, "R3 workbook version."),
    ("r1_repo", False, "The R1 repository this workbook implements."),
    ("r1_source_commit", False, "The pinned R1 commit. Changes only through tools/sync_r1_contracts.py and a rebuild."),
    ("shared_standard_version", False, "Shared standard version pinned through R1."),
    ("calculation_as_of_at", True, "Evaluation time (ISO 8601 UTC, ending in Z) for due states and escalation states. A user-configurable parameter. No formula reads the clock."),
    ("event_reconciliation_from_at", True, "Material changes at or after this time need an Event Log row. A user-configurable parameter."),
    ("selected_org_stage", True, "Organization stage from R1 (startup, early_scale, structured_growth, mature). See config/stage-requirements.yaml."),
    ("operating_mode", True, "starter or full. Same workbook, same model; Starter Mode only reduces what you update each week."),
    ("generated_at", False, "When this file was generated (the pinned R1 synchronization time, so builds are reproducible)."),
)


def settings_rows(settings: dict | None = None) -> list[dict]:
    st = dict(W.settings())
    if settings:
        st.update(settings)
    ref = W.pin_reference()
    values = {
        "workbook_id": st["workbook_id"], "workbook_version": str(st["workbook_version"]), "r1_repo": ref["r1_repo"],
        "r1_source_commit": st["r1_source_commit"], "shared_standard_version": str(st["shared_standard_version"]),
        "calculation_as_of_at": st["calculation_as_of_at"], "event_reconciliation_from_at": st["event_reconciliation_from_at"],
        "selected_org_stage": st["selected_org_stage"], "operating_mode": st["default_operating_mode"], "generated_at": st["generated_at"],
    }
    return [{"setting_key": k, "value": values[k], "editable": "yes" if e else "no", "description": d} for k, e, d in SETTING_ROWS]


def initial_context(inputs: dict | None = None, settings: dict | None = None) -> dict:
    inputs = inputs if inputs is not None else W.load_inputs()
    ctx: dict = {name: [dict(r) for r in rows] for name, rows in inputs.items()}
    srows = settings_rows(settings)
    ctx["tblWorkbookSettings"] = srows
    ctx["settings"] = {r["setting_key"]: r["value"] for r in srows}
    ctx["tblLookupEntries"] = W.lookup_entries()
    ctx["tblReadinessWeights"] = W.readiness_weights()
    ctx["tblRiskBands"] = W.risk_bands()
    ctx["tblRuleParameters"] = W.rule_parameters()
    ctx["tblEscalationRules"] = W.escalation_rules()
    seen = []
    for r in ctx["tblReadiness"]:
        if r["readiness_scorecard_id"] not in seen:
            seen.append(r["readiness_scorecard_id"])
    ctx["tblReadinessSummary"] = [{"readiness_scorecard_id": x} for x in seen]
    ctx["tblCapacitySummary"] = [{"check_key": k, "meaning": m} for k, _, _, m in W.CAPACITY_SUMMARY_ROWS]
    ctx["tblKpiSummary"] = [{"kpi_key": k, "label": lab, "grain": g, "source_table": st, "authority_classification": a}
                            for k, lab, _, _, g, st, a in W.KPI_ROWS]
    n_phase = len(W.lookup_values(ctx["tblLookupEntries"], "phase_key"))
    n_status = len(W.lookup_values(ctx["tblLookupEntries"], "request_status"))
    ctx["tblPhaseSummary"] = [{"position": i} for i in range(1, n_phase + 1)]
    ctx["tblRequestStatusSummary"] = [{"position": i} for i in range(1, n_status + 1)]
    ctx["tblReadinessByProject"] = [{"position": i} for i in range(1, 11)]
    # Input records hold R1's stored values for columns the workbook calculates. Drop
    # them so the reference recomputes every calculated value from inputs alone.
    for name, spec in W.tables().items():
        formula_cols = [c.name for c in spec.columns if c.kind == "formula"]
        for row in ctx.get(name, []):
            for f in formula_cols:
                row.pop(f, None)
    return ctx


def compute(inputs: dict | None = None, settings: dict | None = None) -> dict:
    ctx = initial_context(inputs, settings)
    for name, spec in W.tables().items():
        rows = ctx[name]
        pending = [c for c in spec.columns if c.kind == "formula" and c.py is not None]
        for _ in range(len(pending) + 1):
            if not pending:
                break
            deferred = []
            for column in pending:
                try:
                    values = []
                    for row in rows:
                        if spec.guard and W.blank(row.get(spec.id_column)):
                            values.append("")
                            continue
                        row["__id__"] = row.get(spec.id_column)
                        values.append(column.py(row, ctx))
                except KeyError:
                    deferred.append(column)
                    continue
                for row, value in zip(rows, values):
                    row[column.name] = value
            if len(deferred) == len(pending):
                raise RuntimeError(f"{name}: cannot order formula columns {[c.name for c in deferred]}")
            pending = deferred
        for row in rows:
            row.pop("__id__", None)
        if name == "tblCapacitySummary":
            for row, (_, _, py, _) in zip(rows, W.CAPACITY_SUMMARY_ROWS):
                row["value"] = py(ctx)
        if name == "tblKpiSummary":
            pass
    for row, (_, _, _, py, _, _, _) in zip(ctx["tblKpiSummary"], W.KPI_ROWS):
        row["value"] = py(ctx)
    return ctx


def expected_values(ctx: dict | None = None) -> dict:
    """The expected-values record (verification/expected-values.yaml), traced to R1."""
    ctx = ctx or compute()
    rules = W.r1_rules()
    risk_rules = W.load_yaml("config/risk-rules.yaml")

    def status_counts(table, field="status"):
        out: dict[str, int] = {}
        for r in ctx[table]:
            out[r[field]] = out.get(r[field], 0) + 1
        return dict(sorted(out.items()))

    risks = {}
    for r in ctx["tblRisks"]:
        r1_score = rules.risk_score(r["likelihood"], r["impact"], risk_rules)
        band = rules.risk_band(r1_score, risk_rules)
        risks[r["risk_id"]] = {"likelihood": r["likelihood"], "impact": r["impact"], "risk_score": r["risk_score"],
                               "risk_band": r["risk_band"], "risk_severity": r["risk_severity"],
                               "r1_rule_score": r1_score, "r1_rule_band": band["band"]}
    weights = W.load_yaml("config/readiness-weights.yaml")
    readiness = {}
    for card in ctx["tblReadinessSummary"]:
        entries = {r["category"]: r for r in ctx["tblReadiness"] if r["readiness_scorecard_id"] == card["readiness_scorecard_id"]}
        r1 = rules.readiness_scorecard(entries, weights)
        readiness[card["readiness_scorecard_id"]] = {
            "project_id": card["project_id"], "assessment_purpose": card["assessment_purpose"],
            "overall_score": card["overall_score"], "incomplete_required_evidence_flag": card["incomplete_required_evidence_flag"],
            "r1_rule_overall_score": float(r1["overall_score"]),
            "category_scores": {c: entries[c]["category_score"] for c in entries},
        }
    requests = {r["request_id"]: {"status": r["status"], "escalation_rule_id": r["escalation_rule_id"],
                                  "escalation_due_at": r.get("escalation_due_at") or "", "escalation_due_check": r["escalation_due_check"],
                                  "escalation_due_state": r["escalation_due_state"],
                                  "r1_rule_escalation_due_at": rules.expected_escalation_due_at(r, W.load_yaml("config/sla-rules.yaml")) or ""}
                for r in ctx["tblRequests"]}
    capacity = {r["check_key"]: r["value"] for r in ctx["tblCapacitySummary"]}
    kpi = {r["kpi_key"]: r["value"] for r in ctx["tblKpiSummary"]}
    return {
        "description": ("Expected workbook values for the bundled synthetic data, computed by tools/reference_model.py from the "
                        "pinned R1 inputs. Every r1_rule_* value comes from R1's own pinned tools/r1_rules.py; the workbook "
                        "formula value must equal it. All values are synthetic data, not measured results."),
        "r1_commit": W.pin_reference()["r1_commit"],
        "calculation_as_of_at": ctx["settings"]["calculation_as_of_at"],
        "event_reconciliation_from_at": ctx["settings"]["event_reconciliation_from_at"],
        "record_counts": {t: len(ctx[t]) for t in ("tblProjects", "tblPhases", "tblMilestones", "tblGateAssessments", "tblTasks",
                                                     "tblRequests", "tblHandoffs", "tblRisks", "tblIssues", "tblReadiness",
                                                     "tblCapacityInputs", "tblEventLog", "tblLookupEntries", "tblEscalationRules")},
        "project_status_counts": status_counts("tblProjects", "project_status"),
        "task_status_counts": status_counts("tblTasks"),
        "task_due_states": {r["task_id"]: r["due_state"] for r in ctx["tblTasks"]},
        "task_due_state_counts": status_counts("tblTasks", "due_state"),
        "blocked_tasks": [r["task_id"] for r in ctx["tblTasks"] if r["status"] == "blocked"],
        "risks": risks,
        "requests": requests,
        "readiness": readiness,
        "capacity_inputs": capacity,
        "kpi_summary": kpi,
        "projects_by_phase": {r["phase_key"]: r["project_count"] for r in ctx["tblPhaseSummary"]},
        "requests_by_status": {r["request_status"]: r["request_count"] for r in ctx["tblRequestStatusSummary"]},
        "event_count": len(ctx["tblEventLog"]),
        "event_evidence": {t: {r[W.tables()[t].id_column]: r["event_evidence"] for r in ctx[t]} for t in W.EVIDENCE_TABLES},
    }


if __name__ == "__main__":
    import json
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    print(json.dumps(expected_values()["kpi_summary"], indent=2))
