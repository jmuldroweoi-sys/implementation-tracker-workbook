"""Capacity-input double-count controls.

Proves on fixtures that a workload component is authoritative only once, that duplicates
are flagged and excluded, that informational and excluded rows never add to authoritative
totals, and that a request or handoff that references a task never counts the task's
hours again. One case is also recalculated in LibreOffice."""

from __future__ import annotations

import copy
import json
import unittest

from jsonschema import Draft202012Validator

from support import RM, ROOT, W, needs_libreoffice, reset_root
from test_formulas import recalc_compare


def cpi(n, stype, sid, comp, wtype, method):
    return {"capacity_input_id": f"CPI-{n:06d}", "source_entity_type": stype, "source_entity_id": sid, "workload_component_id": comp,
            "workload_type": wtype, "capacity_inclusion_method": method, "unit": "hours",
            "source_repo": "implementation-operating-system", "source_version": "9acd25a"}


def summary(ctx) -> dict:
    return {r["check_key"]: r["value"] for r in ctx["tblCapacitySummary"]}


class CapacityDoubleCount(unittest.TestCase):
    def setUp(self) -> None:
        reset_root()
        self.base = copy.deepcopy(W.load_inputs())
        self.task_total = sum(t["planned_hours"] for t in self.base["tblTasks"])

    def compute(self, extra_rows=(), replace=None):
        inputs = copy.deepcopy(self.base)
        if replace:
            inputs["tblCapacityInputs"] = [replace.get(r["capacity_input_id"], r) for r in inputs["tblCapacityInputs"]]
        inputs["tblCapacityInputs"] += list(extra_rows)
        return RM.compute(inputs)

    def test_bundled_rows_count_every_task_once(self) -> None:
        s = summary(self.compute())
        self.assertEqual(s["authoritative_planned_hours_total"], self.task_total)
        self.assertEqual(s["hours_reconciliation"], "reconciled")
        self.assertEqual((s["duplicate_authoritative_count"], s["tasks_without_authoritative_row"]), (0, 0))

    def test_component_can_be_authoritative_only_once(self) -> None:
        dup = cpi(901, "request", "REQ-000002", "TSK-000011", "request_handling", "authoritative_workload")
        ctx = self.compute([dup])
        rows = [r for r in ctx["tblCapacityInputs"] if r["workload_component_id"] == "TSK-000011" and r["capacity_inclusion_method"] == "authoritative_workload"]
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(r["duplicate_authoritative_flag"] for r in rows), "both duplicate rows are flagged")
        self.assertTrue(all(r["export_ready_flag"] is False for r in rows), "duplicates are not export ready")
        s = summary(ctx)
        self.assertEqual(s["duplicate_authoritative_count"], 2)
        self.assertEqual(s["hours_reconciliation"], "mismatch", "the totals no longer reconcile, so the problem is visible")

    def test_duplicate_rows_are_rejected_by_the_schema_for_requests(self) -> None:
        schema = json.loads((ROOT / "schemas/r3/capacity-input.schema.json").read_text(encoding="utf-8"))
        row = {"capacity_input_id": "CPI-000901", "period": "2026-09", "project_id": "PRJ-000002", "source_entity_type": "request",
               "source_entity_id": "REQ-000002", "role_id": "ROL-000004", "workload_component_id": "TSK-000011", "workload_type": "request_handling",
               "planned_hours": 4, "actual_hours": 2, "unit": "hours", "capacity_inclusion_method": "authoritative_workload",
               "source_repo": "implementation-operating-system", "source_version": "9acd25a", "org_stage": "early_scale", "export_ready_flag": False}
        self.assertTrue(list(Draft202012Validator(schema).iter_errors(row)), "a request row cannot be authoritative workload")

    def test_informational_rows_do_not_add_to_totals(self) -> None:
        extra = [cpi(902, "phase", "PHS-000002", "PHS-000002", "phase_summary", "informational_only")]
        ctx = self.compute(extra)
        row = next(r for r in ctx["tblCapacityInputs"] if r["capacity_input_id"] == "CPI-000902")
        self.assertGreater(row["planned_hours"], 0, "the informational row still shows its hours")
        self.assertEqual(row["authoritative_planned_hours"], 0)
        self.assertEqual(summary(ctx)["authoritative_planned_hours_total"], self.task_total)

    def test_excluded_rows_do_not_add_to_totals(self) -> None:
        extra = [cpi(903, "handoff", "HND-000002", "TSK-000026", "handoff_effort", "excluded_to_prevent_double_count")]
        ctx = self.compute(extra)
        row = next(r for r in ctx["tblCapacityInputs"] if r["capacity_input_id"] == "CPI-000903")
        self.assertEqual(row["planned_hours"], 8)
        self.assertEqual(row["authoritative_planned_hours"], 0)
        self.assertEqual(summary(ctx)["authoritative_planned_hours_total"], self.task_total)

    def test_request_referencing_a_task_does_not_count_it_again(self) -> None:
        ctx = self.compute()
        req = next(r for r in ctx["tblCapacityInputs"] if r["capacity_input_id"] == "CPI-000031")
        task = next(r for r in ctx["tblCapacityInputs"] if r["capacity_input_id"] == "CPI-000011")
        self.assertEqual(req["workload_component_id"], task["workload_component_id"])
        self.assertEqual(req["planned_hours"], task["planned_hours"])
        self.assertEqual(req["authoritative_planned_hours"], 0)
        self.assertEqual(task["authoritative_planned_hours"], task["planned_hours"])

    def test_missing_task_row_is_reported(self) -> None:
        replace = {"CPI-000005": cpi(5, "task", "TSK-000005", "TSK-000005", "task_effort", "informational_only")}
        s = summary(self.compute(replace=replace))
        self.assertEqual(s["tasks_without_authoritative_row"], 1)
        self.assertEqual(s["hours_reconciliation"], "mismatch")

    @needs_libreoffice
    def test_duplicate_case_recalculates_identically(self) -> None:
        inputs = copy.deepcopy(self.base)
        inputs["tblCapacityInputs"].append(cpi(901, "request", "REQ-000002", "TSK-000011", "request_handling", "authoritative_workload"))
        recalc_compare(self, inputs)


if __name__ == "__main__":
    unittest.main()
