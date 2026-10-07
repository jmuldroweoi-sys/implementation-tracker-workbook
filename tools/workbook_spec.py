"""One definition of the workbook, shared by the builder, the verifier, and the validator.

Every table, column, and formula of implementation-tracker-workbook.xlsx is declared here
once. Each calculated column carries two forms of the same logic:

  excel  the spreadsheet formula written into the workbook
  py     a Python reference implementation, used by tools/reference_model.py to compute
         the value the formula must produce

R1 rules are never reproduced from memory: vocabularies, weights, bands, scales, and rule
parameters are read from the pinned R1 copies under schemas/r1/, and the reference
implementation of R1 calculations calls R1's own pinned tools/r1_rules.py.

Formula conventions (chosen for portability, see verification/portability-checklist.md):
  - no TODAY(), NOW(), OFFSET(), INDIRECT(), LET, LAMBDA, XLOOKUP, or dynamic arrays
  - this-row references use the stored form tblName[[#This Row],[column]]
  - dates and timestamps are ISO 8601 text; comparisons are text comparisons of ISO values
  - the evaluation date is the named cell calculation_as_of_at, never the clock
"""

from __future__ import annotations

import csv
import importlib.util
import json
import re
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Callable

import yaml

ROOT = Path(__file__).resolve().parents[1]
PIN = ROOT / "schemas" / "r1"
R1_REPO = "implementation-operating-system"
R3_REPO = "implementation-tracker-workbook"
WORKBOOK_PATH = ROOT / "workbook" / "implementation-tracker-workbook.xlsx"

SHEETS = (
    "README", "Lookups", "Projects", "Phases and Gates", "Tasks", "Requests and Handoffs",
    "Escalation Rules", "Risks and Issues", "Readiness Scorecard", "Capacity Inputs",
    "Event Log", "KPI Summary",
)
AS_OF = "calculation_as_of_at"
WINDOW = "event_reconciliation_from_at"
FORBIDDEN_FUNCTIONS = ("TODAY", "NOW", "RAND", "RANDBETWEEN", "OFFSET", "INDIRECT", "CELL", "INFO",
                       "LET", "LAMBDA", "XLOOKUP", "XMATCH", "FILTER", "SORT", "SORTBY", "UNIQUE", "SEQUENCE")

# Authority classifications used in FORMULAS.md and the data dictionary.
R1_RULE = "reproduces_r1_rule"
R1_SUMMARY = "summarizes_r1_records"
R3_VIEW = "r3_workbook_validation"


# ---------------------------------------------------------------------------
# Pinned R1 contracts


def load_yaml(rel: str):
    return yaml.safe_load((PIN / rel).read_text(encoding="utf-8"))


def load_json(rel: str):
    return json.loads((PIN / rel).read_text(encoding="utf-8"))


def r1_rules():
    """Import R1's own pinned rule module (schemas/r1/tools/r1_rules.py)."""
    spec = importlib.util.spec_from_file_location("pinned_r1_rules", PIN / "tools" / "r1_rules.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def pin_reference() -> dict:
    return yaml.safe_load((ROOT / "standard" / "standard-reference.yaml").read_text(encoding="utf-8"))


def settings() -> dict:
    return yaml.safe_load((ROOT / "config" / "workbook-settings.yaml").read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Lookups: every list is extracted from a pinned R1 file (or an R3 schema for R3 lists).


def _enum(schema_rel: str, prop: str) -> list[str]:
    doc = load_json(schema_rel)
    spec = doc["properties"].get(prop) or doc["properties"]["categories"]["items"]["properties"][prop]
    return list(spec["enum"])


def _r3_enum(schema_name: str, prop: str) -> list[str]:
    doc = json.loads((ROOT / "schemas" / "r3" / f"{schema_name}.schema.json").read_text(encoding="utf-8"))
    return list(doc["properties"][prop]["enum"])


def _roles() -> list[tuple[str, str]]:
    text = (PIN / "data" / "synthetic" / "README.md").read_text(encoding="utf-8")
    return re.findall(r"^\| `(ROL-\d{6})` \| (\w+) \|", text, re.MULTILINE)


def _event_types() -> list[tuple[str, str]]:
    catalog = {e["event_type"]: e for e in load_yaml("standard/event-catalog.yaml")["events"]}
    used: list[str] = []
    for phase in load_yaml("lifecycle/lifecycle.yaml")["phases"]:
        for ev in phase["emitted_events"]:
            if ev not in used:
                used.append(ev)
    sm = load_yaml("config/request-state-machine.yaml")
    for ev in (sm["initial_event"], sm["transition_event"]):
        if ev not in used:
            used.append(ev)
    for g in load_yaml("lifecycle/gates.yaml")["gates"]:
        if g["emitted_event"] not in used:
            used.append(g["emitted_event"])
    return [(ev, catalog[ev]["subject_type"]) for ev in sorted(used)]


def _rule_ids() -> list[tuple[str, str]]:
    out = [(r["rule_id"], f"config/sla-rules.yaml {r['key']}") for r in load_yaml("config/sla-rules.yaml")["rules"]]
    out += [(r["rule_id"], f"config/lead-time-rules.yaml {r['key']}") for r in load_yaml("config/lead-time-rules.yaml")["rules"]]
    out.append((load_yaml("config/risk-rules.yaml")["rule_id"], "config/risk-rules.yaml risk score"))
    out.append((load_yaml("config/readiness-weights.yaml")["rule_id"], "config/readiness-weights.yaml readiness calculation"))
    return out


def _same(values) -> list[tuple[str, str]]:
    return [(v, v) for v in values]


@dataclass
class LookupSource:
    lookup_type: str
    source_repo: str
    source_path: str
    extract: Callable[[], list[tuple[str, str]]]


LOOKUP_SOURCES = (
    LookupSource("phase_key", R1_REPO, "standard/lifecycle-terms.yaml",
                 lambda: [(p["phase_key"], p["name"]) for p in load_yaml("standard/lifecycle-terms.yaml")["phases"]]),
    LookupSource("phase_status", R1_REPO, "standard/lifecycle-terms.yaml",
                 lambda: _same(load_yaml("standard/lifecycle-terms.yaml")["phase_statuses"])),
    LookupSource("gate_outcome", R1_REPO, "standard/lifecycle-terms.yaml",
                 lambda: _same(load_yaml("standard/lifecycle-terms.yaml")["gate_outcomes"])),
    LookupSource("gate_id", R1_REPO, "lifecycle/gates.yaml",
                 lambda: [(g["gate_id"], g["phase_id"]) for g in load_yaml("lifecycle/gates.yaml")["gates"]]),
    LookupSource("project_status", R1_REPO, "schemas/project.schema.json", lambda: _same(_enum("schemas/project.schema.json", "project_status"))),
    LookupSource("org_stage", R1_REPO, "standard/org-stages.yaml",
                 lambda: _same(s["stage_id"] for s in load_yaml("standard/org-stages.yaml")["stages"])),
    LookupSource("milestone_status", R1_REPO, "schemas/milestone.schema.json", lambda: _same(_enum("schemas/milestone.schema.json", "status"))),
    LookupSource("task_status", R1_REPO, "schemas/task.schema.json", lambda: _same(_enum("schemas/task.schema.json", "status"))),
    LookupSource("request_status", R1_REPO, "config/request-state-machine.yaml",
                 lambda: _same(load_yaml("config/request-state-machine.yaml")["statuses"])),
    LookupSource("request_transition", R1_REPO, "config/request-state-machine.yaml",
                 lambda: [(f"{t['from_status']}>{t['to_status']}", t["performed_by"])
                          for t in load_yaml("config/request-state-machine.yaml")["transitions"]]),
    LookupSource("request_type", R1_REPO, "schemas/request.schema.json", lambda: _same(_enum("schemas/request.schema.json", "request_type"))),
    LookupSource("request_priority", R1_REPO, "schemas/request.schema.json", lambda: _same(_enum("schemas/request.schema.json", "priority"))),
    LookupSource("request_source", R1_REPO, "schemas/request.schema.json", lambda: _same(_enum("schemas/request.schema.json", "source"))),
    LookupSource("handoff_status", R1_REPO, "schemas/handoff.schema.json", lambda: _same(_enum("schemas/handoff.schema.json", "status"))),
    LookupSource("handoff_type", R1_REPO, "schemas/handoff.schema.json", lambda: _same(_enum("schemas/handoff.schema.json", "handoff_type"))),
    LookupSource("risk_status", R1_REPO, "schemas/risk.schema.json", lambda: _same(_enum("schemas/risk.schema.json", "status"))),
    LookupSource("issue_status", R1_REPO, "schemas/issue.schema.json", lambda: _same(_enum("schemas/issue.schema.json", "status"))),
    LookupSource("severity", R1_REPO, "standard/severity-scale.yaml",
                 lambda: [(s["severity_id"], s["display_name"]) for s in load_yaml("standard/severity-scale.yaml")["severities"]]),
    LookupSource("readiness_category", R1_REPO, "standard/readiness-categories.yaml",
                 lambda: [(c["category_id"], c["name"]) for c in load_yaml("standard/readiness-categories.yaml")["categories"]]),
    LookupSource("assessment_purpose", R1_REPO, "schemas/readiness-scorecard.schema.json",
                 lambda: _same(_enum("schemas/readiness-scorecard.schema.json", "assessment_purpose"))),
    LookupSource("actor_type", R1_REPO, "standard/schemas/event.schema.json",
                 lambda: _same(load_json("standard/schemas/event.schema.json")["properties"]["actor_type"]["enum"])),
    LookupSource("event_type", R1_REPO, "standard/event-catalog.yaml", _event_types),
    LookupSource("role_id", R1_REPO, "data/synthetic/README.md", _roles),
    LookupSource("profile_id", R1_REPO, "profiles/examples",
                 lambda: [(d["profile_id"], d["name"]) for d in sorted(
                     (yaml.safe_load(p.read_text(encoding="utf-8")) for p in (PIN / "profiles" / "examples").glob("*.yaml")),
                     key=lambda d: d["profile_id"])]),
    LookupSource("rule_id", R1_REPO, "config", _rule_ids),
    LookupSource("operating_mode", R3_REPO, "schemas/r3/workbook-metadata.schema.json",
                 lambda: _same(_r3_enum("workbook-metadata", "operating_mode"))),
    LookupSource("source_entity_type", R3_REPO, "schemas/r3/capacity-input.schema.json",
                 lambda: _same(_r3_enum("capacity-input", "source_entity_type"))),
    LookupSource("workload_type", R3_REPO, "schemas/r3/capacity-input.schema.json",
                 lambda: _same(_r3_enum("capacity-input", "workload_type"))),
    LookupSource("capacity_inclusion_method", R3_REPO, "schemas/r3/capacity-input.schema.json",
                 lambda: _same(_r3_enum("capacity-input", "capacity_inclusion_method"))),
)


def lookup_entries() -> list[dict]:
    ref = pin_reference()
    rows = []
    for src in LOOKUP_SOURCES:
        version = ref["r1_commit"][:7] if src.source_repo == R1_REPO else settings()["workbook_version"]
        for key, display in src.extract():
            rows.append({
                "lookup_entry_id": f"LKP-{len(rows) + 1:06d}", "lookup_type": src.lookup_type, "key": str(key),
                "display_value": str(display), "source_repo": src.source_repo, "source_path": src.source_path,
                "source_version": version, "active_flag": True,
            })
    return rows


def lookup_values(entries: list[dict], lookup_type: str) -> list[str]:
    return [e["key"] for e in entries if e["lookup_type"] == lookup_type]


# ---------------------------------------------------------------------------
# Mirrored rule parameters (read-only copies of R1 configuration)


def rule_parameters() -> list[dict]:
    rr = load_yaml("config/risk-rules.yaml")
    rw = load_yaml("config/readiness-weights.yaml")
    rows = [
        ("risk_likelihood_min", rr["likelihood_values"]["min"], "config/risk-rules.yaml likelihood_values.min"),
        ("risk_likelihood_max", rr["likelihood_values"]["max"], "config/risk-rules.yaml likelihood_values.max"),
        ("risk_impact_min", rr["impact_values"]["min"], "config/risk-rules.yaml impact_values.min"),
        ("risk_impact_max", rr["impact_values"]["max"], "config/risk-rules.yaml impact_values.max"),
        ("readiness_total_weight", rw["total_weight"], "config/readiness-weights.yaml total_weight"),
        ("readiness_calculation_version", rw["calculation_version"], "config/readiness-weights.yaml calculation_version"),
    ]
    return [{"parameter": p, "value": v, "source_path": s} for p, v, s in rows]


def readiness_weights() -> list[dict]:
    rw = load_yaml("config/readiness-weights.yaml")
    return [{"category": c["category"], "weight": c["weight"], "required_evidence": c["required_evidence"],
             "source_path": "config/readiness-weights.yaml"} for c in rw["categories"]]


def risk_bands() -> list[dict]:
    return [{"band": b["band"], "min_score": b["min_score"], "max_score": b["max_score"], "severity": b["severity"],
             "source_path": "config/risk-rules.yaml"} for b in load_yaml("config/risk-rules.yaml")["bands"]]


def escalation_rules() -> list[dict]:
    rules = r1_rules()
    short = pin_reference()["r1_commit"][:7]
    rows = []
    for r in load_yaml("config/sla-rules.yaml")["rules"]:
        trig = r["trigger"]
        trigger = f"status={trig['status']}" + (f"; severity={trig['severity']}" if "severity" in trig else "")
        if r["action"] == "escalate" and r["enabled_flag"]:
            key = f"{r['applies_to_entity']}|{trig['status']}"
        else:
            key = f"{r['applies_to_entity']}|{trig['status']}|{trig.get('severity', '')}|{r['action']}"
        rows.append({
            "rule_id": r["rule_id"], "source_file": "config/sla-rules.yaml", "source_version": short, "rule_kind": "sla",
            "rule_key": r["key"], "applies_to": r["applies_to_entity"], "trigger": trigger,
            "duration_parameter": r["target_duration"],
            "duration_hours": rules.parse_duration(r["target_duration"]).total_seconds() / 3600,
            "warning_behavior": f"warning {r['warning_offset']} before due",
            "escalation_role_id": r.get("escalation_role_id") or "", "escalation_severity": r.get("escalation_severity") or "",
            "action": r["action"], "enabled": bool(r["enabled_flag"]),
            "stage_behavior": "; ".join(f"{k}={v}" for k, v in r["stage_behavior"].items()), "match_key": key,
        })
    for r in load_yaml("config/lead-time-rules.yaml")["rules"]:
        m = r["match"]
        trigger = (f"{r['rule_type']}; phase_keys={','.join(m['phase_keys']) or 'all'}; "
                   f"critical_only={str(m['critical_only']).lower()}; open_only={str(m['open_only']).lower()}")
        rows.append({
            "rule_id": r["rule_id"], "source_file": "config/lead-time-rules.yaml", "source_version": short,
            "rule_kind": "lead_time", "rule_key": r["key"], "applies_to": "task", "trigger": trigger,
            "duration_parameter": r["lead_time"],
            "duration_hours": rules.parse_duration(r["lead_time"]).total_seconds() / 3600,
            "warning_behavior": "flag only; no warning timer", "escalation_role_id": "", "escalation_severity": "",
            "action": "flag", "enabled": bool(r["enabled_flag"]), "stage_behavior": "not set in R1 for lead-time rules",
            "match_key": f"task|{r['rule_type']}|{r['rule_id']}",
        })
    return rows


# ---------------------------------------------------------------------------
# Input records (the R1 synthetic universe plus R3-only capacity-input rows)


def schema_for(entity: str) -> dict:
    return load_json(f"schemas/{entity}.schema.json")


def read_r1_csv(name: str, entity: str, data_dir: Path | None = None) -> list[dict]:
    base = data_dir or (ROOT / "data" / "synthetic" / "r1")
    _, rows = r1_rules().read_csv_records(base / name, schema_for(entity))
    return rows


def read_events(data_dir: Path | None = None) -> list[dict]:
    base = data_dir or (ROOT / "data" / "synthetic" / "r1")
    return [json.loads(line) for line in (base / "events.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]


def read_capacity_definitions(path: Path | None = None) -> list[dict]:
    path = path or (ROOT / "data" / "synthetic" / "r3" / "capacity-inputs.csv")
    with path.open(encoding="utf-8", newline="") as handle:
        return [dict(r) for r in csv.DictReader(handle)]


def _optional_csv(data_dir: Path | None, name: str, entity: str) -> list[dict]:
    if data_dir and (data_dir / name).is_file():
        return read_r1_csv(name, entity, data_dir)
    return list(schema_for(entity)["examples"])


def load_inputs(data_dir: Path | None = None, capacity_path: Path | None = None) -> dict[str, list[dict]]:
    """Input rows per workbook table, exactly as R1 holds them."""
    return {
        "tblProjects": read_r1_csv("projects.csv", "project", data_dir),
        "tblPhases": read_r1_csv("phases.csv", "phase", data_dir),
        "tblMilestones": read_r1_csv("milestones.csv", "milestone", data_dir),
        # R1 v0.1 holds complete records for these two only, as its schema examples. An
        # adopter's import folder may supply gate-assessments.csv and handoffs.csv instead.
        "tblGateAssessments": _optional_csv(data_dir, "gate-assessments.csv", "gate-assessment"),
        "tblTasks": read_r1_csv("tasks.csv", "task", data_dir),
        "tblRequests": read_r1_csv("requests.csv", "request", data_dir),
        "tblHandoffs": _optional_csv(data_dir, "handoffs.csv", "handoff"),
        "tblRisks": read_r1_csv("risks.csv", "risk", data_dir),
        "tblIssues": read_r1_csv("issues.csv", "issue", data_dir),
        "tblReadiness": read_r1_csv("readiness.csv", "readiness-scorecard", data_dir),
        "tblCapacityInputs": read_capacity_definitions(capacity_path),
        "tblEventLog": [dict(e, payload=json.dumps(e["payload"])) for e in read_events(data_dir)],
    }


# ---------------------------------------------------------------------------
# Excel helpers and Excel-faithful Python helpers


def this(table: str, col: str) -> str:
    return f"{table}[[#This Row],[{col}]]"


def col(table: str, column: str) -> str:
    return f"{table}[{column}]"


def lk(column: str) -> str:
    return f"tblLookupEntries[{column}]"


def xl_serial(ref: str) -> str:
    return f"(DATEVALUE(LEFT({ref},10))+TIMEVALUE(MID({ref},12,8)))"


def blank(v) -> bool:
    return v is None or v == ""


def s(v) -> str:
    """Text value as a cell holds it ("" for empty)."""
    return "" if v is None else str(v)


def num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def excel_round(x: float, places: int) -> float:
    return float(Decimal(repr(x)).quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP))


def serial(ts: str) -> float:
    from datetime import datetime

    d = datetime.strptime(ts[:19], "%Y-%m-%dT%H:%M:%S")
    return (d - datetime(1899, 12, 30)).total_seconds() / 86400


def countifs(rows: list[dict], **criteria) -> int:
    return sum(1 for r in rows if all(r.get(k) == v for k, v in criteria.items()))


def has_event(ctx, subject_id: str, event_type: str) -> bool:
    return any(e["subject_id"] == subject_id and e["event_type"] == event_type for e in ctx["tblEventLog"])


def lk_has(ctx, lookup_type: str, key=None, display=None) -> bool:
    for e in ctx["tblLookupEntries"]:
        if e["lookup_type"] == lookup_type and (key is None or e["key"] == key) and (display is None or e["display_value"] == display):
            return True
    return False


# ---------------------------------------------------------------------------
# Table model


@dataclass
class Column:
    name: str
    kind: str = "input"            # input | formula | mirror
    owner: str = "R1"              # R1 field or R3 helper
    excel: Callable[[str], str] | None = None
    py: Callable[[dict, dict], object] | None = None
    authority: str = ""            # for formula columns
    purpose: str = ""
    edge_cases: str = ""
    validation: str | None = None  # lookup_type for a list validation
    fmt: str | None = None         # number format
    width: int = 14
    export: bool = True            # included in the authoritative export
    required: bool = False


@dataclass
class TableSpec:
    name: str
    sheet: str
    title: str
    entity: str                    # R1 or R3 entity name
    owner: str                     # R1 or R3
    columns: list[Column] = field(default_factory=list)
    guard: bool = True             # formulas return "" when the row's ID is blank
    export_file: str | None = None
    protected: bool = False

    @property
    def id_column(self) -> str:
        return self.columns[0].name

    def column(self, name: str) -> Column:
        return next(c for c in self.columns if c.name == name)


def inputs_from_schema(entity: str, overrides: dict[str, Column] | None = None, widths: dict | None = None) -> list[Column]:
    """R1 schema fields in their CSV column order (or property order), as input columns."""
    doc = schema_for(entity)
    names = doc.get("x-csv-columns") or list(doc["properties"])
    required = set(doc.get("required", []))
    out = []
    for n in names:
        if overrides and n in overrides:
            out.append(overrides[n])
            continue
        spec = doc["properties"].get(n) or doc["properties"].get("categories", {}).get("items", {}).get("properties", {}).get(n, {})
        fmt = "@" if spec.get("type") in ("string", ["string", "null"]) or "array" in str(spec.get("type")) else None
        out.append(Column(n, required=n in required, fmt=fmt, width=(widths or {}).get(n, 14)))
    return out


def evidence_formula(t: str, conditions: list[tuple[str, str, str]], always: str | None = None) -> str:
    """Build an event-evidence formula. conditions: (applies_expr, timestamp_expr, event_type)."""
    parts = []
    in_window = []
    for applies, ts, ev in conditions:
        missing = f'AND({applies},{ts}>={WINDOW},COUNTIFS(tblEventLog[subject_id],{this(t, "__ID__")},tblEventLog[event_type],"{ev}")=0)'
        parts.append((missing, f'"missing:{ev}"'))
        in_window.append(f"AND({applies},{ts}>={WINDOW})")
    expr = f'IF(OR({",".join(in_window)}),"logged","{always or "before_window"}")'
    for missing, label in reversed(parts):
        expr = f"IF({missing},{label},{expr})"
    return expr


def evidence_py(conditions: list[tuple[Callable, Callable, str]], always: str | None = None):
    def f(row, ctx):
        win = ctx["settings"][WINDOW]
        rid = row["__id__"]
        hit = False
        for applies, ts, ev in conditions:
            if applies(row) and s(ts(row)) >= win:
                if not has_event(ctx, rid, ev):
                    return f"missing:{ev}"
                hit = True
        return "logged" if hit else (always or "before_window")
    return f


TRUE = "TRUE"


def _ref_check_project(t):
    return f'IF(COUNTIF(tblProjects[project_id],{this(t, "project_id")})=0,"orphan_project","valid")'


def _ref_check_project_phase(t):
    return (f'IF(COUNTIF(tblProjects[project_id],{this(t, "project_id")})=0,"orphan_project",'
            f'IF(COUNTIFS(tblPhases[phase_id],{this(t, "phase_id")},tblPhases[project_id],{this(t, "project_id")})=0,"orphan_phase","valid"))')


def _py_ref_project(row, ctx):
    return "valid" if countifs(ctx["tblProjects"], project_id=row["project_id"]) else "orphan_project"


def _py_ref_project_phase(row, ctx):
    if not countifs(ctx["tblProjects"], project_id=row["project_id"]):
        return "orphan_project"
    if not countifs(ctx["tblPhases"], phase_id=row.get("phase_id"), project_id=row["project_id"]):
        return "orphan_phase"
    return "valid"


def ref_column(kind: str) -> Column:
    excel = _ref_check_project if kind == "project" else _ref_check_project_phase
    py = _py_ref_project if kind == "project" else _py_ref_project_phase
    return Column("reference_check", "formula", "R3", excel, py, R3_VIEW,
                  "Checks that the referenced project" + (" and phase (same project)" if kind != "project" else "") + " exist in this workbook.",
                  "Returns orphan_project or orphan_phase when a reference does not resolve.", export=False, width=16)


# ---------------------------------------------------------------------------
# Table definitions


def _tables() -> list[TableSpec]:
    T: list[TableSpec] = []

    # README settings
    T.append(TableSpec("tblWorkbookSettings", "README", "Workbook settings (edit the value column only)", "workbook", "R3", [
        Column("setting_key", owner="R3", width=30, fmt="@"), Column("value", owner="R3", width=26, fmt="@"),
        Column("editable", owner="R3", width=10), Column("description", owner="R3", width=70, fmt="@"),
    ], guard=False, export_file=None))

    # Lookups
    T.append(TableSpec("tblLookupEntries", "Lookups", "Lookup entries (synchronized from pinned R1; read-only)", "lookup_entry", "R3", [
        Column("lookup_entry_id", "mirror", "R3", width=15), Column("lookup_type", "mirror", "R3", width=24),
        Column("key", "mirror", "R3", width=26, fmt="@"), Column("display_value", "mirror", "R3", width=30, fmt="@"),
        Column("source_repo", "mirror", "R3", width=28), Column("source_path", "mirror", "R3", width=36),
        Column("source_version", "mirror", "R3", width=12, fmt="@"), Column("active_flag", "mirror", "R3", width=10),
    ], guard=False, protected=True))
    T.append(TableSpec("tblReadinessWeights", "Lookups", "Readiness weights (mirror of R1 config/readiness-weights.yaml)", "readiness_weight", "R1", [
        Column("category", "mirror", width=14), Column("weight", "mirror", width=8),
        Column("required_evidence", "mirror", width=60), Column("source_path", "mirror", width=32),
    ], guard=False, protected=True))
    T.append(TableSpec("tblRiskBands", "Lookups", "Risk bands (mirror of R1 config/risk-rules.yaml)", "risk_band", "R1", [
        Column("band", "mirror", width=10), Column("min_score", "mirror", width=10), Column("max_score", "mirror", width=10),
        Column("severity", "mirror", width=9), Column("source_path", "mirror", width=26),
    ], guard=False, protected=True))
    T.append(TableSpec("tblRuleParameters", "Lookups", "Rule parameters (mirror of R1 configuration)", "rule_parameter", "R1", [
        Column("parameter", "mirror", width=30), Column("value", "mirror", width=10, fmt="@"), Column("source_path", "mirror", width=46),
    ], guard=False, protected=True))

    # Projects
    t = "tblProjects"
    T.append(TableSpec(t, "Projects", "Projects (R1 project records)", "project", "R1", inputs_from_schema("project", widths={"name": 22, "customer_label": 26, "customer_reference": 18}) + [
        Column("current_phase_key", "formula", "R3",
               lambda t: f'IFERROR(INDEX(tblPhases[lifecycle_phase_key],MATCH({this(t, "current_phase_id")},tblPhases[phase_id],0))&"","phase_not_found")',
               lambda r, c: next((p["lifecycle_phase_key"] for p in c["tblPhases"] if p["phase_id"] == r["current_phase_id"]), "phase_not_found"),
               R1_SUMMARY, "Shows the lifecycle phase key of the project's current phase instance.", "phase_not_found when current_phase_id has no phase row.", export=False, width=16),
        Column("reference_check", "formula", "R3",
               lambda t: (f'IF(COUNTIFS(tblPhases[phase_id],{this(t, "current_phase_id")},tblPhases[project_id],{this(t, "project_id")})=0,"orphan_current_phase",'
                          f'IF(COUNTIFS({lk("lookup_type")},"profile_id",{lk("key")},{this(t, "complexity_profile_id")})'
                          f'+COUNTIFS({lk("lookup_type")},"profile_id",{lk("key")},{this(t, "service_profile_id")})'
                          f'+COUNTIFS({lk("lookup_type")},"profile_id",{lk("key")},{this(t, "segment_profile_id")})<3,"orphan_profile","valid"))'),
               lambda r, c: ("orphan_current_phase" if not countifs(c["tblPhases"], phase_id=r["current_phase_id"], project_id=r["project_id"])
                             else "orphan_profile" if sum(lk_has(c, "profile_id", r[k]) for k in ("complexity_profile_id", "service_profile_id", "segment_profile_id")) < 3
                             else "valid"),
               R3_VIEW, "Checks the current phase belongs to this project and the three profile IDs exist.", "orphan_current_phase or orphan_profile.", export=False, width=16),
        Column("event_evidence", "formula", "R3",
               lambda t: evidence_formula(t, [("TRUE", this(t, "created_at"), "project.created")]),
               evidence_py([(lambda r: True, lambda r: r["created_at"], "project.created")]),
               R3_VIEW, "Reconciles project creation against the Event Log.", "before_window when created before event_reconciliation_from_at.", export=False, width=22),
    ], export_file="projects.csv"))

    # Phases and Gates
    t = "tblPhases"
    T.append(TableSpec(t, "Phases and Gates", "Phases (R1 phase instances)", "phase", "R1", inputs_from_schema("phase", widths={"entered_at": 20, "exited_at": 20}) + [
        ref_column("project"),
        Column("gate_check", "formula", "R3",
               lambda t: (f'IF(COUNTIFS({lk("lookup_type")},"gate_id",{lk("display_value")},{this(t, "lifecycle_phase_key")})=0,'
                          f'IF({this(t, "gate_id")}="","valid","unexpected_gate"),'
                          f'IF(COUNTIFS({lk("lookup_type")},"gate_id",{lk("key")},{this(t, "gate_id")},{lk("display_value")},{this(t, "lifecycle_phase_key")})>0,"valid","gate_mismatch"))'),
               lambda r, c: (("valid" if blank(r.get("gate_id")) else "unexpected_gate") if not lk_has(c, "gate_id", display=r["lifecycle_phase_key"])
                             else ("valid" if lk_has(c, "gate_id", key=s(r.get("gate_id")), display=r["lifecycle_phase_key"]) else "gate_mismatch")),
               R1_RULE, "Checks gate_id is the R1 gate for this phase (lifecycle/gates.yaml); Review has none.", "gate_mismatch or unexpected_gate.", export=False),
        Column("event_evidence", "formula", "R3",
               lambda t: evidence_formula(t, [(f'{this(t, "entered_at")}<>""', this(t, "entered_at"), "phase.entered"),
                                              (f'{this(t, "exited_at")}<>""', this(t, "exited_at"), "phase.exited")]),
               evidence_py([(lambda r: not blank(r.get("entered_at")), lambda r: r.get("entered_at"), "phase.entered"),
                            (lambda r: not blank(r.get("exited_at")), lambda r: r.get("exited_at"), "phase.exited")]),
               R3_VIEW, "Reconciles phase entry and exit against the Event Log.", "Checks entry first, then exit.", export=False, width=22),
    ], export_file="phases.csv"))
    t = "tblMilestones"
    T.append(TableSpec(t, "Phases and Gates", "Milestones (R1 milestone records)", "milestone", "R1", inputs_from_schema("milestone", widths={"name": 30}) + [
        ref_column("phase"),
        Column("event_evidence", "formula", "R3",
               lambda t: evidence_formula(t, [(f'{this(t, "status")}="achieved"', this(t, "completed_date") + '&"T23:59:59Z"', "milestone.achieved"),
                                              (f'{this(t, "status")}="missed"', this(t, "target_date") + '&"T23:59:59Z"', "milestone.missed")], "not_required_or_before_window"),
               evidence_py([(lambda r: r["status"] == "achieved", lambda r: s(r.get("completed_date")) + "T23:59:59Z", "milestone.achieved"),
                            (lambda r: r["status"] == "missed", lambda r: s(r.get("target_date")) + "T23:59:59Z", "milestone.missed")], "not_required_or_before_window"),
               R3_VIEW, "Reconciles achieved and missed milestones against the Event Log.", "A date counts as the end of that day when compared with the window timestamp.", export=False, width=24),
    ], export_file="milestones.csv"))
    t = "tblGateAssessments"
    T.append(TableSpec(t, "Phases and Gates", "Gate assessments (R1 records; a person records every outcome)", "gate-assessment", "R1",
                       inputs_from_schema("gate-assessment", widths={"reason": 40, "assessed_at": 20}) + [
        Column("outcome_check", "formula", "R3",
               lambda t: f'IF(COUNTIFS({lk("lookup_type")},"gate_outcome",{lk("key")},{this(t, "outcome")})>0,"valid","invalid_outcome")',
               lambda r, c: "valid" if lk_has(c, "gate_outcome", r["outcome"]) else "invalid_outcome",
               R1_RULE, "Checks the recorded outcome is pass, pass_with_conditions, or hold (standard). It never chooses an outcome.", "invalid_outcome.", export=False),
        Column("assessor_check", "formula", "R3",
               lambda t: f'IF(LEFT({this(t, "assessor_person_id")},4)="PER-","named_person","not_a_person")',
               lambda r, c: "named_person" if s(r["assessor_person_id"]).startswith("PER-") else "not_a_person",
               R1_RULE, "Checks a named person (PER-) recorded the outcome.", "not_a_person for any other ID.", export=False),
        Column("reference_check", "formula", "R3",
               lambda t: (f'IF(COUNTIFS(tblPhases[phase_id],{this(t, "phase_id")},tblPhases[project_id],{this(t, "project_id")})=0,"orphan_phase",'
                          f'IF(COUNTIFS({lk("lookup_type")},"gate_id",{lk("key")},{this(t, "gate_id")},{lk("display_value")},'
                          f'INDEX(tblPhases[lifecycle_phase_key],MATCH({this(t, "phase_id")},tblPhases[phase_id],0)))=0,"gate_phase_mismatch","valid"))'),
               lambda r, c: ("orphan_phase" if not countifs(c["tblPhases"], phase_id=r["phase_id"], project_id=r["project_id"])
                             else "valid" if lk_has(c, "gate_id", r["gate_id"], next(p["lifecycle_phase_key"] for p in c["tblPhases"] if p["phase_id"] == r["phase_id"]))
                             else "gate_phase_mismatch"),
               R3_VIEW, "Checks the phase exists in the project and the gate belongs to that phase.", "orphan_phase or gate_phase_mismatch.", export=False),
        Column("event_evidence", "formula", "R3",
               lambda t: evidence_formula(t, [("TRUE", this(t, "assessed_at"), "gate.assessed")]),
               evidence_py([(lambda r: True, lambda r: r["assessed_at"], "gate.assessed")]),
               R3_VIEW, "Reconciles the assessment against the Event Log.", "before_window for older assessments.", export=False, width=20),
    ], export_file="gate-assessments.csv"))

    # Tasks
    t = "tblTasks"
    T.append(TableSpec(t, "Tasks", "Tasks (R1 task records)", "task", "R1", inputs_from_schema("task", widths={"name": 36, "predecessor_task_ids": 24, "completed_at": 20}) + [
        Column("due_state", "formula", "R3",
               lambda t: (f'IF({this(t, "planned_due_date")}="","no_due_date",IF({this(t, "status")}="cancelled","cancelled",'
                          f'IF({this(t, "status")}="completed",IF(LEFT({this(t, "completed_at")},10)<={this(t, "planned_due_date")},"completed_on_time","completed_late"),'
                          f'IF({this(t, "status")}="blocked","blocked",IF({this(t, "planned_due_date")}<LEFT({AS_OF},10),"overdue","open_not_due")))))'),
               lambda r, c: ("no_due_date" if blank(r.get("planned_due_date")) else "cancelled" if r["status"] == "cancelled"
                             else ("completed_on_time" if s(r.get("completed_at"))[:10] <= r["planned_due_date"] else "completed_late") if r["status"] == "completed"
                             else "blocked" if r["status"] == "blocked"
                             else "overdue" if r["planned_due_date"] < c["settings"][AS_OF][:10] else "open_not_due"),
               R3_VIEW, "Task due state as of calculation_as_of_at.", "Blank due date gives no_due_date; blocked shows blocked even when past due; completed compares the completion date with the due date.", export=False, width=18),
        Column("predecessor_reference_valid", "formula", "R3",
               lambda t: (f'IF({this(t, "predecessor_task_ids")}="","no_predecessor",IF(SUMPRODUCT((tblTasks[task_id]<>"")*ISNUMBER(SEARCH(tblTasks[task_id],{this(t, "predecessor_task_ids")})))'
                          f'=LEN({this(t, "predecessor_task_ids")})-LEN(SUBSTITUTE({this(t, "predecessor_task_ids")},";",""))+1,"valid","invalid"))'),
               lambda r, c: ("no_predecessor" if not r.get("predecessor_task_ids")
                             else "valid" if sum(1 for x in c["tblTasks"] if x["task_id"] and x["task_id"].lower() in ";".join(r["predecessor_task_ids"]).lower()) == len(r["predecessor_task_ids"])
                             else "invalid"),
               R3_VIEW, "Checks every predecessor ID resolves to a task in this workbook.", "Counts listed IDs (semicolons plus one) against IDs found; IDs are fixed length, so one cannot match inside another.", export=False, width=16),
        Column("reference_check", "formula", "R3",
               lambda t: (f'IF(COUNTIF(tblProjects[project_id],{this(t, "project_id")})=0,"orphan_project",'
                          f'IF(COUNTIFS(tblPhases[phase_id],{this(t, "phase_id")},tblPhases[project_id],{this(t, "project_id")})=0,"orphan_phase",'
                          f'IF(AND({this(t, "milestone_id")}<>"",COUNTIFS(tblMilestones[milestone_id],{this(t, "milestone_id")},tblMilestones[project_id],{this(t, "project_id")})=0),"orphan_milestone","valid")))'),
               lambda r, c: (_py_ref_project_phase(r, c) if _py_ref_project_phase(r, c) != "valid"
                             else "orphan_milestone" if r.get("milestone_id") and not countifs(c["tblMilestones"], milestone_id=r["milestone_id"], project_id=r["project_id"])
                             else "valid"),
               R3_VIEW, "Checks project, phase, and milestone references resolve within the same project.", "orphan_project, orphan_phase, or orphan_milestone.", export=False, width=16),
        Column("event_evidence", "formula", "R3",
               lambda t: (f'IF({this(t, "status")}="blocked",IF(COUNTIFS(tblEventLog[subject_id],{this(t, "task_id")},tblEventLog[event_type],"task.status_changed")=0,"missing:task.status_changed","logged"),'
                          + evidence_formula(t, [(f'{this(t, "status")}="completed"', this(t, "completed_at"), "task.status_changed")], "not_required_or_before_window") + ")"),
               lambda r, c: (("logged" if has_event(c, r["task_id"], "task.status_changed") else "missing:task.status_changed") if r["status"] == "blocked"
                             else evidence_py([(lambda x: x["status"] == "completed", lambda x: x.get("completed_at"), "task.status_changed")], "not_required_or_before_window")(r, c)),
               R3_VIEW, "Reconciles completed (inside the window) and blocked tasks against the Event Log.", "Blocked tasks always need a status event.", export=False, width=26),
    ], export_file="tasks.csv"))

    # Requests and Handoffs
    t = "tblRequests"
    esc_hours = f'INDEX(tblEscalationRules[duration_hours],MATCH({this(t, "escalation_rule_id")},tblEscalationRules[rule_id],0))'
    T.append(TableSpec(t, "Requests and Handoffs", "Requests (R1 request records; statuses from R1 config/request-state-machine.yaml)", "request", "R1",
                       inputs_from_schema("request", widths={"description": 40, "submitted_at": 20, "due_at": 20, "status_changed_at": 20, "escalation_due_at": 20}) + [
        Column("status_check", "formula", "R3",
               lambda t: f'IF(COUNTIFS({lk("lookup_type")},"request_status",{lk("key")},{this(t, "status")})>0,"valid","invalid_status")',
               lambda r, c: "valid" if lk_has(c, "request_status", r["status"]) else "invalid_status",
               R1_RULE, "Checks the status is one of the nine R1 request statuses.", "invalid_status.", export=False),
        Column("escalation_rule_id", "formula", "R3",
               lambda t: f'IFERROR(INDEX(tblEscalationRules[rule_id],MATCH("request|"&{this(t, "status")},tblEscalationRules[match_key],0)),"")',
               lambda r, c: next((x["rule_id"] for x in c["tblEscalationRules"] if x["match_key"] == f"request|{r['status']}"), ""),
               R1_RULE, "The enabled R1 escalation rule whose trigger is the request's current status.", "Blank when no rule applies to the status.", export=False),
        Column("escalation_due_check", "formula", "R3",
               lambda t: (f'IF({this(t, "escalation_rule_id")}="",IF({this(t, "escalation_due_at")}="","consistent","unexpected_escalation_due_at"),'
                          f'IF({this(t, "escalation_due_at")}="","missing_escalation_due_at",'
                          f'IF(ABS({xl_serial(this(t, "status_changed_at"))}+{esc_hours}/24-{xl_serial(this(t, "escalation_due_at"))})<0.0001,"consistent","mismatch")))'),
               lambda r, c: _py_escalation_check(r, c),
               R1_RULE, "Recomputes escalation_due_at = status_changed_at + the rule's target duration (R1 config/sla-rules.yaml) and compares.", "Tolerance under 9 seconds absorbs floating-point date arithmetic.", export=False, width=18),
        Column("escalation_due_state", "formula", "R3",
               lambda t: (f'IF({this(t, "status")}="closed","closed",IF({this(t, "escalation_due_at")}="","no_escalation_timer",'
                          f'IF({this(t, "escalation_due_at")}<={AS_OF},"escalation_due","due_later")))'),
               lambda r, c: ("closed" if r["status"] == "closed" else "no_escalation_timer" if blank(r.get("escalation_due_at"))
                             else "escalation_due" if r["escalation_due_at"] <= c["settings"][AS_OF] else "due_later"),
               R3_VIEW, "Whether the request's escalation time has passed as of calculation_as_of_at.", "closed, no_escalation_timer, escalation_due (due at or before the as-of time), due_later.", export=False, width=18),
        ref_column("project"),
        Column("event_evidence", "formula", "R3",
               lambda t: evidence_formula(t, [("TRUE", this(t, "submitted_at"), "request.submitted"),
                                              (f'{this(t, "status")}<>"submitted"', this(t, "status_changed_at"), "request.status_changed")]),
               evidence_py([(lambda r: True, lambda r: r["submitted_at"], "request.submitted"),
                            (lambda r: r["status"] != "submitted", lambda r: r["status_changed_at"], "request.status_changed")]),
               R3_VIEW, "Reconciles submission and the latest status change against the Event Log.", "Submission is checked first.", export=False, width=28),
    ], export_file="requests.csv"))
    t = "tblHandoffs"
    T.append(TableSpec(t, "Requests and Handoffs", "Handoffs (R1 handoff records)", "handoff", "R1",
                       inputs_from_schema("handoff", widths={"required_artifact_refs": 18, "open_item_refs": 16, "requested_at": 20, "accepted_at": 20}) + [
        Column("status_check", "formula", "R3",
               lambda t: f'IF(COUNTIFS({lk("lookup_type")},"handoff_status",{lk("key")},{this(t, "status")})>0,"valid","invalid_status")',
               lambda r, c: "valid" if lk_has(c, "handoff_status", r["status"]) else "invalid_status",
               R1_RULE, "Checks the status is an R1 handoff status.", "invalid_status.", export=False),
        Column("acceptance_check", "formula", "R3",
               lambda t: (f'IF({this(t, "status")}="accepted",IF(AND(LEFT({this(t, "acceptance_person_id")},4)="PER-",{this(t, "accepted_at")}<>""),'
                          f'"named_acceptance","missing_named_acceptance"),"not_accepted")'),
               lambda r, c: (("named_acceptance" if s(r.get("acceptance_person_id")).startswith("PER-") and not blank(r.get("accepted_at")) else "missing_named_acceptance")
                             if r["status"] == "accepted" else "not_accepted"),
               R1_RULE, "Checks an accepted handoff names the person who accepted it (R1 handoff schema).", "missing_named_acceptance.", export=False, width=18),
        ref_column("project"),
        Column("event_evidence", "formula", "R3",
               lambda t: evidence_formula(t, [(f'{this(t, "status")}="accepted"', this(t, "accepted_at"), "handoff.completed")], "not_required_or_before_window"),
               evidence_py([(lambda r: r["status"] == "accepted", lambda r: r.get("accepted_at"), "handoff.completed")], "not_required_or_before_window"),
               R3_VIEW, "Reconciles accepted handoffs against the Event Log.", "Only accepted handoffs need an event.", export=False, width=22),
    ], export_file="handoffs.csv"))

    # Escalation Rules (mirror)
    T.append(TableSpec("tblEscalationRules", "Escalation Rules", "Escalation and lead-time rules (mirror; source of truth: R1 configuration)", "rule", "R1", [
        Column("rule_id", "mirror"), Column("source_file", "mirror", width=28), Column("source_version", "mirror", width=12, fmt="@"),
        Column("rule_kind", "mirror", width=10), Column("rule_key", "mirror", width=28), Column("applies_to", "mirror", width=10),
        Column("trigger", "mirror", width=60), Column("duration_parameter", "mirror", width=12, fmt="@"), Column("duration_hours", "mirror", width=10),
        Column("warning_behavior", "mirror", width=28), Column("escalation_role_id", "mirror", width=14), Column("escalation_severity", "mirror", width=12),
        Column("action", "mirror", width=12), Column("enabled", "mirror", width=9), Column("stage_behavior", "mirror", width=70),
        Column("match_key", "mirror", width=34),
    ], guard=False, protected=True))

    # Risks and Issues
    t = "tblRisks"
    risk_inputs = inputs_from_schema("risk", overrides={"risk_score": Column(
        "risk_score", "formula", "R1",
        lambda t: (f'IF(AND(ISNUMBER({this(t, "likelihood")}),ISNUMBER({this(t, "impact")})),'
                   f'IF(AND({this(t, "likelihood")}=INT({this(t, "likelihood")}),{this(t, "impact")}=INT({this(t, "impact")}),'
                   f'{this(t, "likelihood")}>=risk_likelihood_min,{this(t, "likelihood")}<=risk_likelihood_max,'
                   f'{this(t, "impact")}>=risk_impact_min,{this(t, "impact")}<=risk_impact_max),'
                   f'{this(t, "likelihood")}*{this(t, "impact")},"invalid_scale_value"),"invalid_scale_value")'),
        lambda r, c: _py_risk_score(r, c), R1_RULE,
        "risk_score = likelihood x impact on the configured scale (R1 config/risk-rules.yaml).",
        "invalid_scale_value for blanks, fractions, or values outside the R1 scale.", width=10)}, widths={"title": 34, "description": 40, "mitigation": 40, "identified_at": 20, "resolved_at": 20})
    T.append(TableSpec(t, "Risks and Issues", "Risks (R1 risk records; risk_score is calculated, never typed)", "risk", "R1", risk_inputs + [
        Column("risk_band", "formula", "R3",
               lambda t: f'IF(ISNUMBER({this(t, "risk_score")}),IFERROR(INDEX(tblRiskBands[band],MATCH({this(t, "risk_score")},tblRiskBands[min_score],1)),"no_band"),"invalid_scale_value")',
               lambda r, c: _py_band(r, c, "band"), R1_RULE, "The R1 band whose score range contains risk_score.", "invalid_scale_value when the score is invalid.", export=False, width=12),
        Column("risk_severity", "formula", "R3",
               lambda t: f'IF(ISNUMBER({this(t, "risk_score")}),IFERROR(INDEX(tblRiskBands[severity],MATCH({this(t, "risk_score")},tblRiskBands[min_score],1)),"no_band"),"invalid_scale_value")',
               lambda r, c: _py_band(r, c, "severity"), R1_RULE, "The severity R1 assigns to the band (carried by risk.logged).", "Same as risk_band.", export=False, width=12),
        ref_column("phase"),
        Column("event_evidence", "formula", "R3",
               lambda t: evidence_formula(t, [("TRUE", this(t, "identified_at"), "risk.logged")]),
               evidence_py([(lambda r: True, lambda r: r["identified_at"], "risk.logged")]),
               R3_VIEW, "Reconciles risk logging against the Event Log.", "before_window for older risks.", export=False, width=20),
    ], export_file="risks.csv"))
    t = "tblIssues"
    T.append(TableSpec(t, "Risks and Issues", "Issues (R1 issue records; severity from R1 standard)", "issue", "R1",
                       inputs_from_schema("issue", widths={"title": 34, "description": 40, "resolution": 34, "opened_at": 20, "resolved_at": 20}) + [
        Column("severity_check", "formula", "R3",
               lambda t: f'IF(COUNTIFS({lk("lookup_type")},"severity",{lk("key")},{this(t, "severity")})>0,"valid","invalid_severity")',
               lambda r, c: "valid" if lk_has(c, "severity", r["severity"]) else "invalid_severity",
               R1_RULE, "Checks severity is sev1 to sev4 (R1 standard/severity-scale.yaml).", "invalid_severity.", export=False),
        ref_column("phase"),
        Column("event_evidence", "formula", "R3",
               lambda t: evidence_formula(t, [("TRUE", this(t, "opened_at"), "issue.logged"),
                                              (f'OR({this(t, "status")}="resolved",{this(t, "status")}="closed")', this(t, "resolved_at"), "issue.resolved")]),
               evidence_py([(lambda r: True, lambda r: r["opened_at"], "issue.logged"),
                            (lambda r: r["status"] in ("resolved", "closed"), lambda r: r.get("resolved_at"), "issue.resolved")]),
               R3_VIEW, "Reconciles issue logging and resolution against the Event Log.", "Logging is checked first.", export=False, width=22),
    ], export_file="issues.csv"))

    # Readiness
    t = "tblReadiness"
    rds = this(t, "readiness_scorecard_id")
    readiness_overrides = {
        "weight": Column("weight", "formula", "R1",
                         lambda t: f'IFERROR(INDEX(tblReadinessWeights[weight],MATCH({this(t, "category")},tblReadinessWeights[category],0)),"unknown_category")',
                         lambda r, c: next((w["weight"] for w in c["tblReadinessWeights"] if w["category"] == r["category"]), "unknown_category"),
                         R1_RULE, "The category weight from R1 config/readiness-weights.yaml (mirrored on Lookups).", "unknown_category when the category is not one of the six.", width=8),
        "achieved_rate": Column("achieved_rate", "formula", "R1",
                                lambda t: (f'IF(AND(ISNUMBER({this(t, "criteria_total_count")}),ISNUMBER({this(t, "criteria_met_count")})),'
                                           f'IF(AND({this(t, "criteria_total_count")}>=1,{this(t, "criteria_met_count")}>=0,{this(t, "criteria_met_count")}<={this(t, "criteria_total_count")}),'
                                           f'{this(t, "criteria_met_count")}/{this(t, "criteria_total_count")},"invalid_criteria_counts"),"invalid_criteria_counts")'),
                                lambda r, c: _py_rate(r), R1_RULE, "achieved_rate = criteria_met_count / criteria_total_count (R1).",
                                "invalid_criteria_counts when total is below 1 or met is outside 0 to total; never divides by zero.", fmt="0.0%", width=10),
        "category_score": Column("category_score", "formula", "R1",
                                 lambda t: f'IF(ISNUMBER({this(t, "weighted_result")}),ROUND({this(t, "weighted_result")},2),"")',
                                 lambda r, c: excel_round(r["weighted_result"], 2) if num(r["weighted_result"]) else "",
                                 R1_RULE, "category_score = weight x achieved_rate, rounded half-up to 2 places (R1).", "Blank when the weight or rate is invalid.", width=10),
        "overall_score": Column("overall_score", "formula", "R1",
                                lambda t: (f'IF(COUNTIFS(tblReadiness[readiness_scorecard_id],{rds},tblReadiness[category_count_check],"complete")<>ROWS(tblReadinessWeights[category]),'
                                           f'"incomplete_scorecard",IFERROR(ROUND(100*SUMIFS(tblReadiness[weighted_result],tblReadiness[readiness_scorecard_id],{rds})'
                                           f'/SUMIFS(tblReadiness[weight],tblReadiness[readiness_scorecard_id],{rds}),2),"incomplete_scorecard"))'),
                                lambda r, c: _py_overall(r, c), R1_RULE,
                                "overall_score = 100 x sum(weight x achieved_rate) / sum(weight) for the scorecard, rounded half-up to 2 places (R1).",
                                "incomplete_scorecard unless the scorecard has exactly one row for each of the six categories; never divides by zero.", width=10),
        "incomplete_required_evidence_flag": Column("incomplete_required_evidence_flag", "formula", "R1",
                                                    lambda t: f'COUNTIFS(tblReadiness[readiness_scorecard_id],{rds},tblReadiness[required_evidence_complete_flag],FALSE)>0',
                                                    lambda r, c: any(x["readiness_scorecard_id"] == r["readiness_scorecard_id"] and x["required_evidence_complete_flag"] is False for x in c["tblReadiness"]),
                                                    R1_RULE, "TRUE when any category of the scorecard lacks its required evidence (R1).", "A high score with this flag TRUE is still incomplete.", width=12),
    }
    T.append(TableSpec(t, "Readiness Scorecard", "Readiness entries (R1 readiness rows; calculated columns reproduce R1)", "readiness-scorecard", "R1",
                       inputs_from_schema("readiness-scorecard", overrides=readiness_overrides, widths={"assessed_at": 20, "evidence_refs": 22}) + [
        Column("weighted_result", "formula", "R3",
               lambda t: f'IF(AND(ISNUMBER({this(t, "weight")}),ISNUMBER({this(t, "achieved_rate")})),{this(t, "weight")}*{this(t, "achieved_rate")},"")',
               lambda r, c: r["weight"] * r["achieved_rate"] if num(r["weight"]) and num(r["achieved_rate"]) else "",
               R1_RULE, "weight x achieved_rate before rounding; the overall score sums these (R1).", "Blank when an input is invalid.", export=False, width=10),
        Column("category_count_check", "formula", "R3",
               lambda t: (f'IF(COUNTIF(tblReadiness[readiness_scorecard_id],{rds})<>ROWS(tblReadinessWeights[category]),"missing_or_extra_category",'
                          f'IF(COUNTIFS(tblReadiness[readiness_scorecard_id],{rds},tblReadiness[category],{this(t, "category")})<>1,"duplicate_category",'
                          f'IF(COUNTIF(tblReadinessWeights[category],{this(t, "category")})=0,"unknown_category","complete")))'),
               lambda r, c: _py_cat_check(r, c), R3_VIEW,
               "Checks the scorecard has exactly one row for each R1 readiness category.", "missing_or_extra_category, duplicate_category, unknown_category.", export=False, width=18),
    ], export_file="readiness.csv"))
    # The order of computation matters for the reference model: weighted_result before category_score.
    t = "tblReadinessSummary"
    sid = this(t, "readiness_scorecard_id")

    def first(colname):
        return f'IFERROR(INDEX(tblReadiness[{colname}],MATCH({sid},tblReadiness[readiness_scorecard_id],0)),"scorecard_not_found")'

    T.append(TableSpec(t, "Readiness Scorecard", "Readiness summary (one row per scorecard)", "readiness_summary", "R3", [
        Column("readiness_scorecard_id", owner="R1", width=16),
        Column("project_id", "formula", "R3", lambda t: first("project_id") + '&""', lambda r, c: _py_first(r, c, "project_id"), R1_SUMMARY, "Project of the scorecard.", "scorecard_not_found.", width=12),
        Column("assessment_purpose", "formula", "R3", lambda t: first("assessment_purpose") + '&""', lambda r, c: _py_first(r, c, "assessment_purpose"), R1_SUMMARY, "pre_assessment or launch_review.", "scorecard_not_found.", width=16),
        Column("assessed_at", "formula", "R3", lambda t: first("assessed_at") + '&""', lambda r, c: _py_first(r, c, "assessed_at"), R1_SUMMARY, "When the scorecard was calculated.", "scorecard_not_found.", width=20),
        Column("overall_score", "formula", "R3", lambda t: first("overall_score"), lambda r, c: _py_first(r, c, "overall_score"), R1_RULE, "Overall readiness score (R1 calculation).", "incomplete_scorecard passes through.", width=10),
        Column("incomplete_required_evidence_flag", "formula", "R3", lambda t: first("incomplete_required_evidence_flag"),
               lambda r, c: _py_first(r, c, "incomplete_required_evidence_flag"), R1_RULE, "TRUE when required evidence is incomplete (R1).", "scorecard_not_found.", width=12),
        Column("evidence_warning", "formula", "R3",
               lambda t: (f'IF({this(t, "incomplete_required_evidence_flag")}=TRUE,"Required evidence incomplete: resolve before the human launch decision",'
                          f'IF({this(t, "incomplete_required_evidence_flag")}=FALSE,"Required evidence complete","scorecard_not_found"))'),
               lambda r, c: ("Required evidence incomplete: resolve before the human launch decision" if r["incomplete_required_evidence_flag"] is True
                             else "Required evidence complete" if r["incomplete_required_evidence_flag"] is False else "scorecard_not_found"),
               R3_VIEW, "Plain-language warning. It informs the human reviewer and never records a decision.", "scorecard_not_found.", width=60),
        Column("event_evidence", "formula", "R3",
               lambda t: (f'IF({this(t, "assessed_at")}<{WINDOW},"before_window",IF(COUNTIFS(tblEventLog[subject_id],{sid},tblEventLog[event_type],"readiness.scored")>0,"logged","missing:readiness.scored"))'),
               lambda r, c: ("before_window" if s(r["assessed_at"]) < c["settings"][WINDOW]
                             else "logged" if has_event(c, r["readiness_scorecard_id"], "readiness.scored") else "missing:readiness.scored"),
               R3_VIEW, "Reconciles the scorecard against the Event Log.", "before_window for older scorecards.", width=22),
    ], export_file=None))

    # Capacity Inputs
    t = "tblCapacityInputs"
    comp = this(t, "workload_component_id")
    stype = this(t, "source_entity_type")
    sidc = this(t, "source_entity_id")

    def by_source(task_col, req_col, hnd_col, phs_col):
        return (f'IFERROR(IF({stype}="task",INDEX(tblTasks[{task_col}],MATCH({sidc},tblTasks[task_id],0)),'
                f'IF({stype}="request",INDEX(tblRequests[{req_col}],MATCH({sidc},tblRequests[request_id],0)),'
                f'IF({stype}="handoff",INDEX(tblHandoffs[{hnd_col}],MATCH({sidc},tblHandoffs[handoff_id],0)),'
                f'IF({stype}="phase",INDEX(tblPhases[{phs_col}],MATCH({sidc},tblPhases[phase_id],0)),"source_not_found"))))&"","source_not_found")')

    def hours(colname):
        return (f'IFERROR(IF(LEFT({comp},3)="TSK",INDEX(tblTasks[{colname}],MATCH({comp},tblTasks[task_id],0))*1,'
                f'IF(LEFT({comp},3)="PHS",SUMIFS(tblTasks[{colname}],tblTasks[phase_id],{comp}),"component_not_found")),"component_not_found")')

    T.append(TableSpec(t, "Capacity Inputs", "Capacity inputs (R3 export for future R2; no capacity math here)", "capacity-input", "R3", [
        Column("capacity_input_id", owner="R3", width=14),
        Column("period", "formula", "R3",
               lambda t: (f'IFERROR(IF(LEFT({comp},3)="TSK",LEFT(INDEX(tblTasks[planned_due_date],MATCH({comp},tblTasks[task_id],0))&"",7),'
                          f'LEFT(INDEX(tblPhases[entered_at],MATCH({comp},tblPhases[phase_id],0))&"",7)),"")'),
               lambda r, c: _py_period(r, c), R3_VIEW, "Month (YYYY-MM) of the component's planned due date, or of the phase entry for a phase summary.",
               "Blank when the component is missing.", width=9),
        Column("project_id", "formula", "R3", lambda t: by_source("project_id", "project_id", "project_id", "project_id"),
               lambda r, c: _py_by_source(r, c, "project_id", "project_id", "project_id", "project_id"), R1_SUMMARY,
               "Project of the source record.", "source_not_found when the source record does not exist.", width=12),
        Column("source_entity_type", owner="R3", validation="source_entity_type", width=12),
        Column("source_entity_id", owner="R3", width=14),
        Column("role_id", "formula", "R3", lambda t: by_source("owner_role_id", "owner_role_id", "to_role_id", "owner_role_id"),
               lambda r, c: _py_by_source(r, c, "owner_role_id", "owner_role_id", "to_role_id", "owner_role_id"), R1_SUMMARY,
               "Role carrying the work: task or request owner, handoff receiving role, or phase owner.", "source_not_found.", width=12),
        Column("workload_component_id", owner="R3", width=14),
        Column("workload_type", owner="R3", validation="workload_type", width=14),
        Column("planned_hours", "formula", "R3", lambda t: hours("planned_hours"), lambda r, c: _py_hours(r, c, "planned_hours"), R1_SUMMARY,
               "Planned hours of the workload component (a task, or the sum of a phase's tasks). Copied from R1 task data; never estimated here.",
               "component_not_found; a blank task value counts as 0.", width=9),
        Column("actual_hours", "formula", "R3", lambda t: hours("actual_hours"), lambda r, c: _py_hours(r, c, "actual_hours"), R1_SUMMARY,
               "Actual hours of the workload component.", "Same as planned_hours.", width=9),
        Column("unit", owner="R3", width=7),
        Column("capacity_inclusion_method", owner="R3", validation="capacity_inclusion_method", width=30),
        Column("source_repo", owner="R3", width=28),
        Column("source_version", owner="R3", width=10, fmt="@"),
        Column("org_stage", "formula", "R3",
               lambda t: f'IFERROR(INDEX(tblProjects[org_stage],MATCH({this(t, "project_id")},tblProjects[project_id],0))&"","")',
               lambda r, c: next((p["org_stage"] for p in c["tblProjects"] if p["project_id"] == r["project_id"]), ""), R1_SUMMARY,
               "Organization stage of the source project.", "Blank when the project is missing.", width=16),
        Column("export_ready_flag", "formula", "R3",
               lambda t: (f'AND(NOT({this(t, "duplicate_authoritative_flag")}),ISNUMBER({this(t, "planned_hours")}),ISNUMBER({this(t, "actual_hours")}),'
                          f'{this(t, "unit")}="hours",{this(t, "project_id")}<>"source_not_found",'
                          f'COUNTIFS({lk("lookup_type")},"capacity_inclusion_method",{lk("key")},{this(t, "capacity_inclusion_method")})>0)'),
               lambda r, c: (not r["duplicate_authoritative_flag"] and num(r["planned_hours"]) and num(r["actual_hours"]) and r["unit"] == "hours"
                             and r["project_id"] != "source_not_found" and lk_has(c, "capacity_inclusion_method", r["capacity_inclusion_method"])),
               R3_VIEW, "TRUE when the row can be exported: no duplicate authoritative component, numeric hours, unit hours, known source and method.",
               "FALSE rows stay visible for correction.", width=10),
        Column("duplicate_authoritative_flag", "formula", "R3",
               lambda t: (f'AND({this(t, "capacity_inclusion_method")}="authoritative_workload",'
                          f'COUNTIFS(tblCapacityInputs[workload_component_id],{comp},tblCapacityInputs[capacity_inclusion_method],"authoritative_workload")>1)'),
               lambda r, c: (r["capacity_inclusion_method"] == "authoritative_workload"
                             and countifs(c["tblCapacityInputs"], workload_component_id=r["workload_component_id"], capacity_inclusion_method="authoritative_workload") > 1),
               R3_VIEW, "TRUE when a workload component is authoritative in more than one row. Every such row is excluded from totals.",
               "Both duplicate rows are flagged.", export=False, width=10),
        Column("authoritative_planned_hours", "formula", "R3",
               lambda t: (f'IF(AND({this(t, "capacity_inclusion_method")}="authoritative_workload",NOT({this(t, "duplicate_authoritative_flag")}),'
                          f'ISNUMBER({this(t, "planned_hours")})),{this(t, "planned_hours")},0)'),
               lambda r, c: (r["planned_hours"] if r["capacity_inclusion_method"] == "authoritative_workload" and not r["duplicate_authoritative_flag"] and num(r["planned_hours"]) else 0),
               R3_VIEW, "Planned hours that count toward the authoritative total; 0 for informational, excluded, or duplicate rows.", "Prevents double counting.", export=False, width=10),
        Column("authoritative_actual_hours", "formula", "R3",
               lambda t: (f'IF(AND({this(t, "capacity_inclusion_method")}="authoritative_workload",NOT({this(t, "duplicate_authoritative_flag")}),'
                          f'ISNUMBER({this(t, "actual_hours")})),{this(t, "actual_hours")},0)'),
               lambda r, c: (r["actual_hours"] if r["capacity_inclusion_method"] == "authoritative_workload" and not r["duplicate_authoritative_flag"] and num(r["actual_hours"]) else 0),
               R3_VIEW, "Actual hours that count toward the authoritative total.", "Same as authoritative_planned_hours.", export=False, width=10),
    ], export_file="capacity-inputs.csv"))
    T.append(TableSpec("tblCapacitySummary", "Capacity Inputs", "Capacity input checks (R3 view; not capacity, utilization, or staffing)", "capacity_summary", "R3", [
        Column("check_key", owner="R3", width=36), Column("value", "formula", "R3", width=12), Column("meaning", owner="R3", width=60),
    ], guard=False))

    # Event Log
    t = "tblEventLog"
    p = this(t, "payload")

    def extract(key):
        k = f'"""{key}"": """'
        return f'IFERROR(MID({p},FIND({k},{p})+{len(key) + 5},FIND("""",{p},FIND({k},{p})+{len(key) + 5})-FIND({k},{p})-{len(key) + 5}),"")'

    T.append(TableSpec(t, "Event Log", "Event Log (shared event contract; entered or imported, never auto-appended)", "event", "R1", [
        Column("event_id", width=13), Column("event_type", width=24, validation="event_type"), Column("occurred_at", width=20, fmt="@"),
        Column("actor_id", width=12), Column("actor_type", width=10, validation="actor_type"), Column("subject_type", width=18),
        Column("subject_id", width=13), Column("payload", width=60, fmt="@"), Column("source_repo", width=28), Column("schema_version", width=10, fmt="@"),
        Column("event_type_check", "formula", "R3",
               lambda t: (f'IF(COUNTIFS({lk("lookup_type")},"event_type",{lk("key")},{this(t, "event_type")})=0,"not_registered_for_v0_1",'
                          f'IF(COUNTIFS({lk("lookup_type")},"event_type",{lk("key")},{this(t, "event_type")},{lk("display_value")},{this(t, "subject_type")})=0,"subject_type_mismatch","registered"))'),
               lambda r, c: ("not_registered_for_v0_1" if not lk_has(c, "event_type", r["event_type"])
                             else "registered" if lk_has(c, "event_type", r["event_type"], r["subject_type"]) else "subject_type_mismatch"),
               R1_RULE, "Checks the event type is an R1 v0.1 event and its subject type matches the R1 catalog.", "not_registered_for_v0_1 or subject_type_mismatch.", export=False, width=18),
        Column("source_repo_check", "formula", "R3",
               lambda t: f'IF({this(t, "source_repo")}="{R1_REPO}","catalog_producer","wrong_source_repo")',
               lambda r, c: "catalog_producer" if r["source_repo"] == R1_REPO else "wrong_source_repo",
               R1_RULE, "Every v0.1 event is produced by R1; the workbook records R1 events and never produces its own.", "wrong_source_repo.", export=False, width=16),
        Column("actor_check", "formula", "R3",
               lambda t: (f'IF({this(t, "actor_type")}="human",IF(LEFT({this(t, "actor_id")},4)="PER-","valid","human_actor_not_person"),'
                          f'IF({this(t, "actor_type")}="system",IF(COUNTIFS({lk("lookup_type")},"rule_id",{lk("key")},{this(t, "actor_id")})>0,"valid","unknown_system_actor"),'
                          f'IF({this(t, "actor_type")}="ai_agent","ai_actor_not_used_in_v0_1","invalid_actor_type")))'),
               lambda r, c: (("valid" if r["actor_id"].startswith("PER-") else "human_actor_not_person") if r["actor_type"] == "human"
                             else ("valid" if lk_has(c, "rule_id", r["actor_id"]) else "unknown_system_actor") if r["actor_type"] == "system"
                             else "ai_actor_not_used_in_v0_1" if r["actor_type"] == "ai_agent" else "invalid_actor_type"),
               R1_RULE, "Human actors are PER- people; system actors are configured R1 rules; no AI actor in v0.1.", "One of four failure labels.", export=False, width=14),
        Column("subject_check", "formula", "R3", lambda t: _subject_excel(t), lambda r, c: _py_subject(r, c), R3_VIEW,
               "Checks the event subject exists in the matching workbook table.", "event_only_record for gate assessments and handoffs that R1 holds only as events.", export=False, width=18),
        Column("payload_check", "formula", "R3",
               lambda t: f'IF(AND(LEFT(TRIM({p}),1)="{{",RIGHT(TRIM({p}),1)="}}"),"object_text","not_json_object")',
               lambda r, c: "object_text" if r["payload"].strip().startswith("{") and r["payload"].strip().endswith("}") else "not_json_object",
               R3_VIEW, "Shape check that payload is a JSON object. Full JSON and schema validation runs in tools/validate.py.", "not_json_object.", export=False, width=14),
        Column("request_transition_check", "formula", "R3",
               lambda t: (f'IF({this(t, "event_type")}<>"request.status_changed","not_applicable",'
                          f'IF(COUNTIFS({lk("lookup_type")},"request_transition",{lk("key")},{extract("from_status")}&">"&{extract("to_status")})>0,"legal","illegal"))'),
               lambda r, c: _py_transition(r, c), R1_RULE,
               "For request.status_changed, checks from_status > to_status is a legal R1 transition (config/request-state-machine.yaml).",
               "Reads the payload text written in the standard JSON form; illegal when the pair is missing.", export=False, width=16),
    ], export_file="event-log.csv"))

    # KPI Summary
    T.append(TableSpec("tblKpiSummary", "KPI Summary", "KPI summary (operational view; not a metric authority)", "kpi", "R3", [
        Column("kpi_key", owner="R3", width=34), Column("label", owner="R3", width=44), Column("value", "formula", "R3", width=10),
        Column("grain", owner="R3", width=12), Column("source_table", owner="R3", width=26), Column("authority_classification", owner="R3", width=26),
    ], guard=False, protected=True))
    T.append(TableSpec("tblPhaseSummary", "KPI Summary", "Projects by current phase", "phase_summary", "R3", [
        Column("position", owner="R3", width=9),
        Column("phase_key", "formula", "R3", lambda t: f'IFERROR(INDEX(lst_phase_key,{this(t, "position")}),"")',
               lambda r, c: _py_lookup_at(c, "phase_key", r["position"]), R1_SUMMARY, "The lifecycle phase at this position (R1 order).", "Blank past the last phase.", width=12),
        Column("project_count", "formula", "R3", lambda t: f'COUNTIF(tblProjects[current_phase_key],{this(t, "phase_key")})',
               lambda r, c: countifs(c["tblProjects"], current_phase_key=r["phase_key"]), R1_SUMMARY, "Projects whose current phase is this phase.", "0 when none.", width=10),
    ], guard=False, protected=True))
    T.append(TableSpec("tblRequestStatusSummary", "KPI Summary", "Requests by status", "request_status_summary", "R3", [
        Column("position", owner="R3", width=9),
        Column("request_status", "formula", "R3", lambda t: f'IFERROR(INDEX(lst_request_status,{this(t, "position")}),"")',
               lambda r, c: _py_lookup_at(c, "request_status", r["position"]), R1_SUMMARY, "The R1 request status at this position.", "Blank past the last status.", width=18),
        Column("request_count", "formula", "R3", lambda t: f'COUNTIF(tblRequests[status],{this(t, "request_status")})',
               lambda r, c: countifs(c["tblRequests"], status=r["request_status"]), R1_SUMMARY, "Requests in this status.", "0 when none.", width=10),
    ], guard=False, protected=True))
    T.append(TableSpec("tblReadinessByProject", "KPI Summary", "Readiness by project", "readiness_by_project", "R3", [
        Column("position", owner="R3", width=9),
        Column("project_id", "formula", "R3", lambda t: f'IFERROR(INDEX(tblProjects[project_id],{this(t, "position")})&"","")',
               lambda r, c: c["tblProjects"][r["position"] - 1]["project_id"] if r["position"] <= len(c["tblProjects"]) else "", R1_SUMMARY,
               "The project at this position on the Projects tab.", "Blank past the last project.", width=12),
        Column("readiness_score", "formula", "R3",
               lambda t: f'IF({this(t, "project_id")}="","",IFERROR(INDEX(tblReadinessSummary[overall_score],MATCH({this(t, "project_id")},tblReadinessSummary[project_id],0)),"no_assessment"))',
               lambda r, c: "" if not r["project_id"] else next((x["overall_score"] for x in c["tblReadinessSummary"] if x["project_id"] == r["project_id"]), "no_assessment"),
               R1_SUMMARY, "Overall score of the project's first listed scorecard. It informs human review only.", "no_assessment when the project has no scorecard.", width=10),
        Column("evidence_warning", "formula", "R3",
               lambda t: f'IF({this(t, "project_id")}="","",IFERROR(INDEX(tblReadinessSummary[evidence_warning],MATCH({this(t, "project_id")},tblReadinessSummary[project_id],0)),"no_assessment"))',
               lambda r, c: "" if not r["project_id"] else next((x["evidence_warning"] for x in c["tblReadinessSummary"] if x["project_id"] == r["project_id"]), "no_assessment"),
               R1_SUMMARY, "The scorecard's required-evidence warning.", "no_assessment.", width=60),
    ], guard=False, protected=True))
    return T


# ---------------------------------------------------------------------------
# Python helpers for the reference implementation


def _py_escalation_check(r, c):
    rule = r["escalation_rule_id"]
    due = r.get("escalation_due_at")
    if rule == "":
        return "consistent" if blank(due) else "unexpected_escalation_due_at"
    if blank(due):
        return "missing_escalation_due_at"
    hours = next(x["duration_hours"] for x in c["tblEscalationRules"] if x["rule_id"] == rule)
    return "consistent" if abs(serial(r["status_changed_at"]) + hours / 24 - serial(due)) < 0.0001 else "mismatch"


def _param(c, name):
    return next(p["value"] for p in c["tblRuleParameters"] if p["parameter"] == name)


def _py_risk_score(r, c):
    li, im = r.get("likelihood"), r.get("impact")
    if not (num(li) and num(im)):
        return "invalid_scale_value"
    if li != int(li) or im != int(im):
        return "invalid_scale_value"
    if not (_param(c, "risk_likelihood_min") <= li <= _param(c, "risk_likelihood_max") and _param(c, "risk_impact_min") <= im <= _param(c, "risk_impact_max")):
        return "invalid_scale_value"
    return li * im


def _py_band(r, c, key):
    score = r["risk_score"]
    if not num(score):
        return "invalid_scale_value"
    eligible = [b for b in c["tblRiskBands"] if b["min_score"] <= score]
    return eligible[-1][key] if eligible else "no_band"


def _py_rate(r):
    total, met = r.get("criteria_total_count"), r.get("criteria_met_count")
    if not (num(total) and num(met)) or total < 1 or not 0 <= met <= total:
        return "invalid_criteria_counts"
    return met / total


def _py_cat_check(r, c):
    rows = [x for x in c["tblReadiness"] if x["readiness_scorecard_id"] == r["readiness_scorecard_id"]]
    if len(rows) != len(c["tblReadinessWeights"]):
        return "missing_or_extra_category"
    if sum(1 for x in rows if x["category"] == r["category"]) != 1:
        return "duplicate_category"
    if not any(w["category"] == r["category"] for w in c["tblReadinessWeights"]):
        return "unknown_category"
    return "complete"


def _py_overall(r, c):
    rows = [x for x in c["tblReadiness"] if x["readiness_scorecard_id"] == r["readiness_scorecard_id"]]
    if sum(1 for x in rows if x["category_count_check"] == "complete") != len(c["tblReadinessWeights"]):
        return "incomplete_scorecard"
    w = sum(x["weight"] for x in rows if num(x["weight"]))
    if not w:
        return "incomplete_scorecard"
    return excel_round(100 * sum(x["weighted_result"] for x in rows if num(x["weighted_result"])) / w, 2)


def _py_first(r, c, key):
    row = next((x for x in c["tblReadiness"] if x["readiness_scorecard_id"] == r["readiness_scorecard_id"]), None)
    return "scorecard_not_found" if row is None else row[key]


def _py_period(r, c):
    comp = r["workload_component_id"]
    if comp.startswith("TSK"):
        row = next((x for x in c["tblTasks"] if x["task_id"] == comp), None)
        return s(row.get("planned_due_date"))[:7] if row else ""
    row = next((x for x in c["tblPhases"] if x["phase_id"] == comp), None)
    return s(row.get("entered_at"))[:7] if row else ""


def _py_by_source(r, c, task_col, req_col, hnd_col, phs_col):
    table = {"task": ("tblTasks", "task_id", task_col), "request": ("tblRequests", "request_id", req_col),
             "handoff": ("tblHandoffs", "handoff_id", hnd_col), "phase": ("tblPhases", "phase_id", phs_col)}.get(r["source_entity_type"])
    if not table:
        return "source_not_found"
    row = next((x for x in c[table[0]] if x[table[1]] == r["source_entity_id"]), None)
    return "source_not_found" if row is None else s(row.get(table[2]))


def _py_hours(r, c, key):
    comp = r["workload_component_id"]
    if comp.startswith("TSK"):
        row = next((x for x in c["tblTasks"] if x["task_id"] == comp), None)
        if row is None:
            return "component_not_found"
        v = row.get(key)
        return v if num(v) else 0
    if comp.startswith("PHS"):
        return sum(x[key] for x in c["tblTasks"] if x["phase_id"] == comp and num(x.get(key)))
    return "component_not_found"


SUBJECT_TABLES = (("PRJ", "tblProjects", "project_id"), ("PHS", "tblPhases", "phase_id"), ("MLS", "tblMilestones", "milestone_id"),
                  ("TSK", "tblTasks", "task_id"), ("REQ", "tblRequests", "request_id"), ("RSK", "tblRisks", "risk_id"),
                  ("ISS", "tblIssues", "issue_id"), ("RDS", "tblReadinessSummary", "readiness_scorecard_id"),
                  ("GAT", "tblGateAssessments", "gate_assessment_id"), ("HND", "tblHandoffs", "handoff_id"))
EVENT_ONLY_PREFIXES = ("GAT", "HND")


def _subject_excel(t):
    sid = this(t, "subject_id")
    expr = '"unsupported_subject"'
    for prefix, table, key in reversed(SUBJECT_TABLES):
        miss = '"event_only_record"' if prefix in EVENT_ONLY_PREFIXES else '"missing"'
        expr = f'IF(LEFT({sid},3)="{prefix}",IF(COUNTIF({table}[{key}],{sid})>0,"found",{miss}),{expr})'
    return expr


def _py_subject(r, c):
    sid = r["subject_id"]
    for prefix, table, key in SUBJECT_TABLES:
        if sid.startswith(prefix):
            if countifs(c[table], **{key: sid}):
                return "found"
            return "event_only_record" if prefix in EVENT_ONLY_PREFIXES else "missing"
    return "unsupported_subject"


def _py_transition(r, c):
    if r["event_type"] != "request.status_changed":
        return "not_applicable"
    payload = json.loads(r["payload"])
    key = f"{payload.get('from_status', '')}>{payload.get('to_status', '')}"
    return "legal" if lk_has(c, "request_transition", key) else "illegal"


def _py_lookup_at(c, lookup_type, position):
    values = lookup_values(c["tblLookupEntries"], lookup_type)
    return values[position - 1] if 1 <= position <= len(values) else ""


# ---------------------------------------------------------------------------
# Summary rows (formulas whose rows are fixed metrics rather than records)

EVIDENCE_TABLES = ("tblProjects", "tblPhases", "tblMilestones", "tblGateAssessments", "tblTasks", "tblRequests",
                   "tblHandoffs", "tblRisks", "tblIssues", "tblReadinessSummary")
REFERENCE_TABLES = ("tblProjects", "tblPhases", "tblMilestones", "tblGateAssessments", "tblTasks", "tblRequests",
                    "tblHandoffs", "tblRisks", "tblIssues")


def _missing_evidence_excel():
    return "+".join(f'COUNTIF({t}[event_evidence],"missing*")' for t in EVIDENCE_TABLES)


def _reference_problem_excel():
    parts = [f'COUNTIFS({t}[{TABLES[t].id_column}],"?*",{t}[reference_check],"<>valid")' for t in REFERENCE_TABLES]
    return "+".join(parts)


# key, label, excel, py, grain, source_table, authority
KPI_ROWS = (
    ("project_count", "Projects", 'COUNTIF(tblProjects[project_id],"?*")', lambda c: len(c["tblProjects"]), "workbook", "tblProjects", R1_SUMMARY),
    ("active_project_count", "Active projects", 'COUNTIF(tblProjects[project_status],"active")',
     lambda c: countifs(c["tblProjects"], project_status="active"), "workbook", "tblProjects", R1_SUMMARY),
    ("open_task_count", "Open tasks (not completed or cancelled)", 'COUNTIFS(tblTasks[task_id],"?*",tblTasks[status],"<>completed",tblTasks[status],"<>cancelled")',
     lambda c: sum(1 for x in c["tblTasks"] if x["status"] not in ("completed", "cancelled")), "workbook", "tblTasks", R1_SUMMARY),
    ("blocked_task_count", "Blocked tasks", 'COUNTIF(tblTasks[status],"blocked")', lambda c: countifs(c["tblTasks"], status="blocked"), "workbook", "tblTasks", R1_SUMMARY),
    ("overdue_task_count", "Overdue tasks as of calculation_as_of_at", 'COUNTIF(tblTasks[due_state],"overdue")',
     lambda c: countifs(c["tblTasks"], due_state="overdue"), "workbook", "tblTasks", R3_VIEW),
    ("open_risk_count", "Open risks (open or mitigating)", 'COUNTIF(tblRisks[status],"open")+COUNTIF(tblRisks[status],"mitigating")',
     lambda c: sum(1 for x in c["tblRisks"] if x["status"] in ("open", "mitigating")), "workbook", "tblRisks", R1_SUMMARY),
    ("open_issue_count", "Open issues (open or in progress)", 'COUNTIF(tblIssues[status],"open")+COUNTIF(tblIssues[status],"in_progress")',
     lambda c: sum(1 for x in c["tblIssues"] if x["status"] in ("open", "in_progress")), "workbook", "tblIssues", R1_SUMMARY),
    ("request_count", "Requests", 'COUNTIF(tblRequests[request_id],"?*")', lambda c: len(c["tblRequests"]), "workbook", "tblRequests", R1_SUMMARY),
    ("escalation_due_request_count", "Requests whose escalation time has passed", 'COUNTIF(tblRequests[escalation_due_state],"escalation_due")',
     lambda c: countifs(c["tblRequests"], escalation_due_state="escalation_due"), "workbook", "tblRequests", R3_VIEW),
    ("readiness_scorecard_count", "Readiness scorecards", 'COUNTIF(tblReadinessSummary[readiness_scorecard_id],"?*")',
     lambda c: len(c["tblReadinessSummary"]), "workbook", "tblReadinessSummary", R1_SUMMARY),
    ("incomplete_readiness_evidence_count", "Scorecards with incomplete required evidence", 'COUNTIF(tblReadinessSummary[incomplete_required_evidence_flag],TRUE)',
     lambda c: sum(1 for x in c["tblReadinessSummary"] if x["incomplete_required_evidence_flag"] is True), "workbook", "tblReadinessSummary", R1_SUMMARY),
    ("event_log_row_count", "Event Log rows", 'COUNTIF(tblEventLog[event_id],"?*")', lambda c: len(c["tblEventLog"]), "workbook", "tblEventLog", R1_SUMMARY),
    ("event_log_problem_count", "Event Log rows failing a check",
     'COUNTIFS(tblEventLog[event_id],"?*",tblEventLog[event_type_check],"<>registered")+COUNTIFS(tblEventLog[event_id],"?*",tblEventLog[actor_check],"<>valid")'
     '+COUNTIF(tblEventLog[subject_check],"missing")+COUNTIF(tblEventLog[source_repo_check],"wrong_source_repo")+COUNTIF(tblEventLog[request_transition_check],"illegal")',
     lambda c: (sum(1 for x in c["tblEventLog"] if x["event_type_check"] != "registered") + sum(1 for x in c["tblEventLog"] if x["actor_check"] != "valid")
                + countifs(c["tblEventLog"], subject_check="missing") + countifs(c["tblEventLog"], source_repo_check="wrong_source_repo")
                + countifs(c["tblEventLog"], request_transition_check="illegal")), "workbook", "tblEventLog", R3_VIEW),
    ("missing_event_evidence_count", "Material changes inside the window with no Event Log row", None,
     lambda c: sum(1 for t in EVIDENCE_TABLES for x in c[t] if str(x.get("event_evidence", "")).startswith("missing")), "workbook", "all record tables", R3_VIEW),
    ("reference_problem_count", "Records with an unresolved reference", None,
     lambda c: sum(1 for t in REFERENCE_TABLES for x in c[t] if x.get("reference_check") != "valid"), "workbook", "all record tables", R3_VIEW),
)

# key, excel, py, meaning
CAPACITY_SUMMARY_ROWS = (
    ("authoritative_planned_hours_total", "SUM(tblCapacityInputs[authoritative_planned_hours])",
     lambda c: sum(x["authoritative_planned_hours"] for x in c["tblCapacityInputs"]), "Planned hours counted once, from authoritative rows only."),
    ("authoritative_actual_hours_total", "SUM(tblCapacityInputs[authoritative_actual_hours])",
     lambda c: sum(x["authoritative_actual_hours"] for x in c["tblCapacityInputs"]), "Actual hours counted once, from authoritative rows only."),
    ("task_planned_hours_total", "SUM(tblTasks[planned_hours])",
     lambda c: sum(x["planned_hours"] for x in c["tblTasks"] if num(x.get("planned_hours"))), "Planned hours on the Tasks tab, for reconciliation."),
    ("task_actual_hours_total", "SUM(tblTasks[actual_hours])",
     lambda c: sum(x["actual_hours"] for x in c["tblTasks"] if num(x.get("actual_hours"))), "Actual hours on the Tasks tab, for reconciliation."),
    ("hours_reconciliation", 'IF(AND(ABS(SUM(tblCapacityInputs[authoritative_planned_hours])-SUM(tblTasks[planned_hours]))<0.0001,'
                             'ABS(SUM(tblCapacityInputs[authoritative_actual_hours])-SUM(tblTasks[actual_hours]))<0.0001),"reconciled","mismatch")',
     lambda c: "reconciled" if (abs(sum(x["authoritative_planned_hours"] for x in c["tblCapacityInputs"]) - sum(x["planned_hours"] for x in c["tblTasks"] if num(x.get("planned_hours")))) < 1e-4
                                and abs(sum(x["authoritative_actual_hours"] for x in c["tblCapacityInputs"]) - sum(x["actual_hours"] for x in c["tblTasks"] if num(x.get("actual_hours")))) < 1e-4) else "mismatch",
     "reconciled when authoritative totals equal the task totals: every task counted exactly once."),
    ("authoritative_row_count", 'COUNTIF(tblCapacityInputs[capacity_inclusion_method],"authoritative_workload")',
     lambda c: countifs(c["tblCapacityInputs"], capacity_inclusion_method="authoritative_workload"), "Rows that carry authoritative workload."),
    ("informational_row_count", 'COUNTIF(tblCapacityInputs[capacity_inclusion_method],"informational_only")',
     lambda c: countifs(c["tblCapacityInputs"], capacity_inclusion_method="informational_only"), "Rows exported for context; ignored by capacity math."),
    ("excluded_row_count", 'COUNTIF(tblCapacityInputs[capacity_inclusion_method],"excluded_to_prevent_double_count")',
     lambda c: countifs(c["tblCapacityInputs"], capacity_inclusion_method="excluded_to_prevent_double_count"), "Rows that repeat a task's work and are excluded."),
    ("duplicate_authoritative_count", "COUNTIF(tblCapacityInputs[duplicate_authoritative_flag],TRUE)",
     lambda c: sum(1 for x in c["tblCapacityInputs"] if x["duplicate_authoritative_flag"] is True), "Rows claiming an already-authoritative component; must be 0."),
    ("tasks_without_authoritative_row",
     'SUMPRODUCT((tblTasks[task_id]<>"")*(COUNTIFS(tblCapacityInputs[workload_component_id],tblTasks[task_id],tblCapacityInputs[capacity_inclusion_method],"authoritative_workload")=0))',
     lambda c: sum(1 for x in c["tblTasks"] if not countifs(c["tblCapacityInputs"], workload_component_id=x["task_id"], capacity_inclusion_method="authoritative_workload")),
     "Tasks with no authoritative capacity row; must be 0 before export."),
    ("export_ready_row_count", "COUNTIF(tblCapacityInputs[export_ready_flag],TRUE)",
     lambda c: sum(1 for x in c["tblCapacityInputs"] if x["export_ready_flag"] is True), "Rows ready to export."),
)

TABLES: dict[str, TableSpec] = {}


def tables() -> dict[str, TableSpec]:
    if not TABLES:
        for spec in _tables():
            TABLES[spec.name] = spec
    return TABLES


def kpi_excel(key: str, excel: str | None) -> str:
    if key == "missing_event_evidence_count":
        return _missing_evidence_excel()
    if key == "reference_problem_count":
        return _reference_problem_excel()
    return excel


def formula_for(spec: TableSpec, column: Column) -> str:
    expr = column.excel(spec.name).replace("__ID__", spec.id_column)
    if spec.guard:
        expr = f'IF({this(spec.name, spec.id_column)}="","",{expr})'
    return "=" + expr


def formula_names(text: str) -> set[str]:
    """Function names used in a formula string."""
    stripped = re.sub(r'"[^"]*"', '""', text)
    return set(re.findall(r"\b([A-Z][A-Z0-9.]*)\(", stripped))
