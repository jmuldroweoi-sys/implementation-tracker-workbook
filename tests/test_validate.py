"""Negative tests for tools/validate.py.

Each test copies the repository into a temporary folder, breaks exactly one thing, and
confirms the matching check fails. The committed repository is never modified."""

from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path

from support import ROOT, Sandbox, reset_root, table_cell

import validate  # noqa: E402  (tools/ is on the path through support)

EM_DASH = chr(0x2014)


class RealRepository(unittest.TestCase):
    def test_real_repository_passes_every_check(self) -> None:
        try:
            res = validate.validate(ROOT)
        finally:
            reset_root()
        self.assertEqual([(c, n) for c, ok, n in res.rows if not ok], [])
        self.assertEqual(len(res.rows), 38)


class Negative(unittest.TestCase):
    def setUp(self) -> None:
        self.box = Sandbox()

    def tearDown(self) -> None:
        self.box.close()

    def assertFails(self, check: str, contains: str | None = None, blocklist=None) -> None:
        results = self.box.run(blocklist)
        self.assertIn(check, results)
        ok, note = results[check]
        self.assertFalse(ok, f"{check} should fail")
        if contains:
            self.assertIn(contains, note)

    def set_cell(self, table, row_id, column, value) -> None:
        self.box.edit_workbook(lambda wb: setattr(table_cell(wb, table, row_id, column), "value", value))

    # Pins and sources
    def test_altered_r1_schema_copy(self) -> None:
        self.box.replace("schemas/r1/schemas/risk.schema.json", '"minimum": 1', '"minimum": 0')
        self.assertFails("R04", "SHA-256 differs")

    def test_altered_r1_synthetic_input(self) -> None:
        self.box.replace("data/synthetic/r1/risks.csv", ",4,3,12,", ",4,4,12,")
        self.assertFails("R05", "SHA-256 differs")

    def test_changed_readiness_weight_in_pinned_config(self) -> None:
        self.box.replace("schemas/r1/config/readiness-weights.yaml", "weight: 25", "weight: 30")
        self.assertFails("R04")

    def test_changed_readiness_weight_in_workbook_mirror(self) -> None:
        self.set_cell("tblReadinessWeights", "technology", "weight", 30)
        self.assertFails("R13", "tblReadinessWeights differs")

    def test_validation_list_drift(self) -> None:
        self.box.replace("config/validation-lists.yaml", "  - on_hold\n", "  - paused\n")
        self.assertFails("R13", "drifted")

    # Vocabulary values held in the workbook
    def test_unsupported_project_status(self) -> None:
        self.set_cell("tblProjects", "PRJ-000001", "project_status", "paused")
        self.assertFails("R14", "project_status 'paused'")

    def test_invalid_phase_key(self) -> None:
        self.set_cell("tblPhases", "PHS-000002", "lifecycle_phase_key", "planning")
        self.assertFails("R14", "lifecycle_phase_key 'planning'")

    def test_invalid_gate_outcome(self) -> None:
        self.set_cell("tblGateAssessments", "GAT-000002", "outcome", "approved")
        self.assertFails("R14", "outcome 'approved'")

    def test_invalid_event_type(self) -> None:
        self.set_cell("tblEventLog", "EVT-000001", "event_type", "project.opened")
        self.assertFails("R24", "not_registered_for_v0_1")

    # Formulas
    def test_incorrect_risk_formula(self) -> None:
        def change(wb):
            cell = table_cell(wb, "tblRisks", "RSK-000001", "risk_score")
            cell.value = cell.value.replace('*tblRisks[[#This Row],[impact]]', '+tblRisks[[#This Row],[impact]]')
        self.box.edit_workbook(change)
        self.assertFails("R11", "formula differs")

    def test_volatile_today(self) -> None:
        self.set_cell("tblTasks", "TSK-000001", "due_state", '=IF(TODAY()>0,"overdue","")')
        self.assertFails("R12", "uses TODAY")

    def test_volatile_now(self) -> None:
        self.box.edit_workbook(lambda wb: wb["KPI Summary"].cell(row=40, column=20, value="=NOW()"))
        self.assertFails("R12", "uses NOW")

    def test_external_link(self) -> None:
        self.box.edit_workbook(lambda wb: wb["KPI Summary"].cell(row=40, column=20, value="='[other.xlsx]Sheet1'!A1"))
        self.assertFails("R34")

    def test_macro_part(self) -> None:
        p = self.box.path("workbook/implementation-tracker-workbook.xlsx")
        with zipfile.ZipFile(p, "a") as z:
            z.writestr("xl/vbaProject.bin", b"\x00")
        self.assertFails("R35")

    # Capacity, references, events
    def test_duplicate_authoritative_capacity_component(self) -> None:
        self.set_cell("tblCapacityInputs", "CPI-000031", "capacity_inclusion_method", "authoritative_workload")
        self.assertFails("R21", "TSK-000011 authoritative more than once")

    def test_orphan_task_reference(self) -> None:
        self.set_cell("tblTasks", "TSK-000012", "milestone_id", "MLS-000099")
        self.assertFails("R16", "MLS-000099")

    def test_malformed_payload_json(self) -> None:
        self.set_cell("tblEventLog", "EVT-000005", "payload", '{"project_id": "PRJ-000001", "from_status": ')
        self.assertFails("R23", "not valid JSON")

    # Sheets
    def test_extra_sheet(self) -> None:
        self.box.edit_workbook(lambda wb: wb.create_sheet("Scratch"))
        self.assertFails("R09")

    def test_missing_sheet(self) -> None:
        self.box.edit_workbook(lambda wb: wb.remove(wb["KPI Summary"]))
        self.assertFails("R09")

    def test_wrong_sheet_order(self) -> None:
        self.box.edit_workbook(lambda wb: wb.move_sheet("Tasks", offset=1))
        self.assertFails("R09")

    def test_hidden_sheet(self) -> None:
        self.box.edit_workbook(lambda wb: setattr(wb["Lookups"], "sheet_state", "hidden"))
        self.assertFails("R08")

    # Documentation and public safety
    def test_em_dash(self) -> None:
        self.box.replace("docs/starter-mode.md", "Starter Mode is how", f"Starter Mode {EM_DASH} is how")
        self.assertFails("R31")

    def test_blocklisted_term(self) -> None:
        self.box.replace("docs/starter-mode.md", "Starter Mode is how", "Starter Mode at ExampleCorpZeta is how")
        with tempfile.TemporaryDirectory() as tmp:
            bl = Path(tmp) / "blocklist.txt"
            bl.write_text("# illustrative example\nExampleCorpZeta\n", encoding="utf-8")
            self.assertFails("R32", "1 file(s) contain a private term", blocklist=[str(bl)])

    def test_clean_blocklist_reports_count(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bl = Path(tmp) / "blocklist.txt"
            bl.write_text("ExampleCorpZeta\n", encoding="utf-8")
            ok, note = self.box.run([str(bl)])["R32"]
        self.assertTrue(ok)
        self.assertIn("1 private terms loaded; 0 hits", note)

    def test_readme_without_ai_assistance(self) -> None:
        self.box.replace("README.md", "## AI assistance", "## Tools used")
        self.assertFails("R27")

    def test_label_near_variant(self) -> None:
        self.box.replace("docs/starter-mode.md", "a proposed design value, not a measured result.", "a proposed design value.")
        self.assertFails("R29")

    def test_vendor_matcher_is_whole_word_and_case_sensitive(self) -> None:
        # The list is stored as hashes, so these assertions pin its matching behavior.
        self.assertTrue(validate.names_listed_vendor("We track work in " + "Hub" + "Spot today."))
        self.assertTrue(validate.names_listed_vendor("Boards like " + "Monday" + ".com are out of scope."))
        self.assertFalse(validate.names_listed_vendor("the no" + "tion of a sl" + "ack schedule"))  # common words, lowercase
        self.assertFalse(validate.names_listed_vendor("Salesforcelike tooling"))

    def test_vendor_name(self) -> None:
        vendor = "Sales" + "force"  # assembled so this file never spells out a vendor name
        self.assertTrue(validate.names_listed_vendor(vendor))
        self.box.replace("docs/starter-mode.md", "Starter Mode is how", "Starter Mode in " + vendor + " is how")
        self.assertFails("R30")

    def test_secret(self) -> None:
        fake = "gh" + "p_" + "A" * 36
        self.box.replace("docs/starter-mode.md", "Starter Mode is how", f"Starter Mode {fake} is how")
        self.assertFails("R33")

    def test_duplicated_r1_authority(self) -> None:
        self.box.path("config/lifecycle.yaml").write_text("phases: [initiate, discover]\n", encoding="utf-8")
        self.assertFails("R36", "which R1 owns")

    def test_stale_expected_values(self) -> None:
        self.box.replace("verification/expected-values.yaml", "event_count: 38", "event_count: 39")
        self.assertFails("R38", "stale")

    def test_practical_workflow_step_missing(self) -> None:
        self.box.replace("docs/practical-workflow.md", "### Step 14. Verify workbook", "### Step 14. Finish")
        self.assertFails("R28", "verify workbook")


if __name__ == "__main__":
    unittest.main()
