"""Deterministic rules of the R1 v0.1 core.

Every calculation and rule check in R1 lives here as a plain function with no side
effects: the same inputs always give the same output. tools/validate.py and the tests
call these functions; R3 mirrors them as spreadsheet formulas. No function here uses
AI, randomness, the network, or the current clock (callers pass any date they need).

Functions:
  parse_duration             ISO 8601 durations used by the configuration (PT24H, P5D)
  risk_score, risk_band      config/risk-rules.yaml
  request_transition_allowed config/request-state-machine.yaml
  phase_move_allowed         lifecycle/lifecycle.yaml (legal next phases, gate outcomes)
  gate_outcome_valid         standard/lifecycle-terms.yaml gate outcomes
  readiness_weight_problems  config/readiness-weights.yaml
  readiness_scorecard        config/readiness-weights.yaml calculation
  sla_rule_for, sla_timer    config/sla-rules.yaml
  expected_escalation_due_at config/sla-rules.yaml applied to a request
  lead_time_flags            config/lead-time-rules.yaml
  GATE_CHECKS                deterministic checks named in lifecycle/gates.yaml
  reference_problems         referential integrity across the R1 records
"""

from __future__ import annotations

import csv
import re
from datetime import date, datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

DURATION_RE = re.compile(r"^P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?)?$")
ID_RE = re.compile(r"^[A-Z]{3}-[0-9]{6}$")
TWO_PLACES = Decimal("0.01")


# ---------------------------------------------------------------------------
# Parsing helpers


def parse_duration(text: str) -> timedelta:
    """Parse the ISO 8601 duration subset used in configuration: PnD, PTnH, PTnM, and
    combinations such as P1DT4H. Raises ValueError for anything else."""
    match = DURATION_RE.match(str(text))
    if not match or text in ("P", "PT") or str(text).endswith("T"):
        raise ValueError(f"not a supported ISO 8601 duration: {text!r}")
    days, hours, minutes = (int(g) if g else 0 for g in match.groups())
    return timedelta(days=days, hours=hours, minutes=minutes)


def parse_timestamp(text: str) -> datetime:
    """Parse a UTC timestamp ending in Z."""
    if not str(text).endswith("Z"):
        raise ValueError(f"timestamp is not UTC with Z: {text!r}")
    return datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def format_timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_date(text: str) -> date:
    return date.fromisoformat(text)


def read_csv_records(path: Path, schema: dict) -> tuple[list[str], list[dict]]:
    """Read a CSV file and convert each row to a typed record using the JSON Schema
    property types. An empty cell is null where the schema allows null, otherwise the
    field is omitted (standard/field-conventions.md). Arrays are split on semicolons."""
    props = dict(schema.get("properties", {}))
    item_props = props.get("categories", {}).get("items", {}).get("properties", {})
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        header = list(reader.fieldnames or [])
        rows = []
        for raw in reader:
            record = {}
            for key, cell in raw.items():
                spec = props.get(key) or item_props.get(key) or {}
                types = spec.get("type", "string")
                types = types if isinstance(types, list) else [types]
                if cell is None or cell == "":
                    if "null" in types:
                        record[key] = None
                    continue
                if "array" in types:
                    record[key] = cell.split(";")
                elif "boolean" in types:
                    if cell not in ("true", "false"):
                        record[key] = cell
                    else:
                        record[key] = cell == "true"
                elif "integer" in types:
                    record[key] = int(cell) if re.fullmatch(r"-?\d+", cell) else cell
                elif "number" in types:
                    if re.fullmatch(r"-?\d+", cell):
                        record[key] = int(cell)
                    elif re.fullmatch(r"-?\d+\.\d+", cell):
                        record[key] = float(cell)
                    else:
                        record[key] = cell
                else:
                    record[key] = cell
            rows.append(record)
    return header, rows


# ---------------------------------------------------------------------------
# Risk


def risk_score(likelihood: int, impact: int, rules: dict) -> int:
    """risk_score = likelihood x impact, after checking both are on the configured scale."""
    for name, value in (("likelihood", likelihood), ("impact", impact)):
        scale = rules[f"{name}_values"]
        if isinstance(value, bool) or not isinstance(value, int) or not scale["min"] <= value <= scale["max"]:
            raise ValueError(f"{name} {value!r} is outside {scale['min']} to {scale['max']}")
    return likelihood * impact


def risk_band(score: int, rules: dict) -> dict:
    """Return the band whose min_score <= score <= max_score."""
    for band in rules["bands"]:
        if band["min_score"] <= score <= band["max_score"]:
            return band
    raise ValueError(f"risk score {score} is in no band")


def risk_band_problems(rules: dict) -> list[str]:
    """Bands must cover 1 to max x max with no gap or overlap, in order."""
    top = rules["likelihood_values"]["max"] * rules["impact_values"]["max"]
    expected = 1
    problems = []
    for band in rules["bands"]:
        if band["min_score"] != expected:
            problems.append(f"band {band['band']} starts at {band['min_score']}, expected {expected}")
        if band["max_score"] < band["min_score"]:
            problems.append(f"band {band['band']} ends before it starts")
        expected = band["max_score"] + 1
    if expected != top + 1:
        problems.append(f"bands end at {expected - 1}, expected {top}")
    return problems


# ---------------------------------------------------------------------------
# Requests, phases, gates


def request_transition_allowed(from_status: str, to_status: str, machine: dict) -> bool:
    """True only when config/request-state-machine.yaml lists the transition."""
    return any(t["from_status"] == from_status and t["to_status"] == to_status for t in machine["transitions"])


def phase_move_allowed(from_key: str, to_key: str, gate_outcome: str | None, lifecycle: dict) -> bool:
    """A phase move is legal when the target is a legal next phase and, for a forward
    move, the current phase's gate outcome is pass or pass_with_conditions. The listed
    rework move (validate to build) needs no passing outcome."""
    phases = {p["phase_id"]: p for p in lifecycle["phases"]}
    if from_key not in phases or to_key not in phases:
        return False
    if to_key not in phases[from_key]["legal_next_phase_ids"]:
        return False
    rules = lifecycle["phase_move_rules"]
    rework = any(m["from_phase_id"] == from_key and m["to_phase_id"] == to_key for m in rules["rework_moves"])
    if rework:
        return True
    if phases[to_key]["order"] <= phases[from_key]["order"]:
        return False
    return gate_outcome in rules["forward_move_requires_gate_outcomes"]


def gate_outcome_valid(outcome: object, allowed: list[str]) -> bool:
    return isinstance(outcome, str) and outcome in allowed


# ---------------------------------------------------------------------------
# Readiness


def readiness_weight_problems(config: dict, canonical: list[str]) -> list[str]:
    cats = config.get("categories") or []
    names = [c.get("category") for c in cats]
    problems = []
    if names != canonical:
        problems.append("categories differ from the six canonical readiness categories")
    weights = [c.get("weight") for c in cats]
    if any(isinstance(w, bool) or not isinstance(w, (int, float)) or w <= 0 for w in weights):
        problems.append("every weight must be a positive number")
    elif Decimal(str(sum(Decimal(str(w)) for w in weights))) != Decimal(str(config.get("total_weight"))):
        problems.append(f"weights total {sum(weights)}, declared total_weight is {config.get('total_weight')}")
    for c in cats:
        if not c.get("required_evidence"):
            problems.append(f"{c.get('category')}: no required_evidence")
    return problems


def _round(value: Decimal) -> Decimal:
    return value.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def readiness_scorecard(entries: dict[str, dict], config: dict) -> dict:
    """Calculate a scorecard from per-category inputs.

    entries maps category to {criteria_total_count, criteria_met_count,
    required_evidence_complete_flag}. Returns achieved_rate and category_score per
    category, overall_score, and incomplete_required_evidence_flag. All arithmetic is
    exact decimal arithmetic, rounded half-up to two places at the end."""
    weights = {c["category"]: Decimal(str(c["weight"])) for c in config["categories"]}
    if set(entries) != set(weights):
        raise ValueError("entries must cover exactly the configured categories")
    total = sum(weights.values())
    weighted = Decimal(0)
    out: dict = {"categories": {}}
    incomplete = False
    for category, weight in weights.items():
        e = entries[category]
        met, count = e["criteria_met_count"], e["criteria_total_count"]
        if count < 1 or not 0 <= met <= count:
            raise ValueError(f"{category}: criteria_met_count must be between 0 and criteria_total_count")
        rate = Decimal(met) / Decimal(count)
        weighted += weight * rate
        out["categories"][category] = {
            "weight": weight,
            "achieved_rate": rate,
            "category_score": _round(weight * rate),
        }
        if not e["required_evidence_complete_flag"]:
            incomplete = True
    out["overall_score"] = _round(Decimal(100) * weighted / total)
    out["incomplete_required_evidence_flag"] = incomplete
    return out


# ---------------------------------------------------------------------------
# SLA timers


def sla_rule_for(entity: str, status: str, severity: str | None, sla: dict) -> dict | None:
    """The enabled rule whose trigger matches the entity, status, and (for issues)
    severity. Configuration validation guarantees at most one match."""
    for rule in sla["rules"]:
        trig = rule["trigger"]
        if rule["applies_to_entity"] != entity or not rule.get("enabled_flag"):
            continue
        if trig.get("status") != status:
            continue
        if "severity" in trig and trig["severity"] != severity:
            continue
        return rule
    return None


def sla_timer(rule: dict, starts_at: datetime) -> tuple[datetime, datetime]:
    """Return (warning_at, due_at) for a timer that starts at starts_at."""
    due = starts_at + parse_duration(rule["target_duration"])
    return due - parse_duration(rule["warning_offset"]), due


def expected_escalation_due_at(request: dict, sla: dict) -> str | None:
    """escalation_due_at for a request: status_changed_at plus the target_duration of
    the enabled request rule for its current status, or None when no rule applies."""
    rule = sla_rule_for("request", request["status"], None, sla)
    if not rule or rule.get("action") != "escalate":
        return None
    _, due = sla_timer(rule, parse_timestamp(request["status_changed_at"]))
    return format_timestamp(due)


# ---------------------------------------------------------------------------
# Lead-time rules


def lead_time_flags(data: dict[str, list[dict]], config: dict) -> list[tuple[str, str, str]]:
    """Return sorted (rule_id, task_id, message) flags for planned work scheduled too
    late. Dates only; no status or date is changed."""
    projects = {p["project_id"]: p for p in data["projects"]}
    phases = {p["phase_id"]: p for p in data["phases"]}
    milestones = {m["milestone_id"]: m for m in data["milestones"]}
    tasks = {t["task_id"]: t for t in data["tasks"]}
    flags = []
    for rule in config["rules"]:
        if not rule.get("enabled_flag"):
            continue
        lead = parse_duration(rule["lead_time"])
        match = rule.get("match") or {}
        for task in data["tasks"]:
            phase = phases.get(task.get("phase_id"), {})
            if match.get("phase_keys") and phase.get("lifecycle_phase_key") not in match["phase_keys"]:
                continue
            if match.get("critical_only") and not task.get("critical_flag"):
                continue
            if match.get("open_only") and task.get("status") in ("completed", "cancelled"):
                continue
            due = task.get("planned_due_date")
            start = task.get("planned_start_date")
            kind = rule["rule_type"]
            if kind == "due_before_target_launch":
                launch = projects.get(task["project_id"], {}).get("target_launch_date")
                if due and launch and parse_date(due) > parse_date(launch) - lead:
                    flags.append((rule["rule_id"], task["task_id"], f"due {due} is later than {lead.days} day(s) before target launch {launch}"))
            elif kind == "due_before_milestone":
                ms = milestones.get(task.get("milestone_id") or "")
                if due and ms and parse_date(due) > parse_date(ms["target_date"]) - lead:
                    flags.append((rule["rule_id"], task["task_id"], f"due {due} is later than milestone {ms['milestone_id']} target {ms['target_date']}"))
            elif kind == "start_after_predecessors":
                for pred_id in task.get("predecessor_task_ids") or []:
                    pred = tasks.get(pred_id)
                    if start and pred and pred.get("planned_due_date") and parse_date(start) < parse_date(pred["planned_due_date"]) + lead:
                        flags.append((rule["rule_id"], task["task_id"], f"starts {start} before predecessor {pred_id} is due {pred['planned_due_date']}"))
            else:
                raise ValueError(f"unknown rule_type {kind}")
    return sorted(flags)


# ---------------------------------------------------------------------------
# Gate checks (inform the human assessor; never decide)


def _check_critical_tasks_closed(project_id, phase_id, data, ctx):
    return all(t["status"] in ("completed", "cancelled") for t in data["tasks"]
               if t["phase_id"] == phase_id and t.get("critical_flag"))


def _check_critical_milestones_achieved(project_id, phase_id, data, ctx):
    return all(m["status"] == "achieved" for m in data["milestones"]
               if m["phase_id"] == phase_id and m.get("critical_flag"))


def _check_no_open_sev1_sev2_issues(project_id, phase_id, data, ctx):
    return not any(i["project_id"] == project_id and i["severity"] in ("sev1", "sev2")
                   and i["status"] in ("open", "in_progress") for i in data["issues"])


def _check_no_open_critical_risks(project_id, phase_id, data, ctx):
    return not any(r["project_id"] == project_id and r["status"] == "open"
                   and risk_band(r["risk_score"], ctx["risk_rules"])["band"] == "critical" for r in data["risks"])


def _check_no_blocked_requests(project_id, phase_id, data, ctx):
    return not any(r["project_id"] == project_id and r["status"] == "blocked" for r in data["requests"])


def _launch_scorecards(project_id, data):
    cards = [c for c in data.get("scorecards", []) if c["project_id"] == project_id and c["assessment_purpose"] == "launch_review"]
    return sorted(cards, key=lambda c: c["assessed_at"])


def _check_readiness_scored(project_id, phase_id, data, ctx):
    return bool(_launch_scorecards(project_id, data))


def _check_required_evidence_complete(project_id, phase_id, data, ctx):
    cards = _launch_scorecards(project_id, data)
    return bool(cards) and not cards[-1]["incomplete_required_evidence_flag"]


def _check_handoff_accepted(project_id, phase_id, data, ctx):
    return any(h["project_id"] == project_id and h["handoff_type"] == "transition" and h["status"] == "accepted"
               for h in data.get("handoffs", []))


GATE_CHECKS = {
    "critical_tasks_closed": _check_critical_tasks_closed,
    "critical_milestones_achieved": _check_critical_milestones_achieved,
    "no_open_sev1_sev2_issues": _check_no_open_sev1_sev2_issues,
    "no_open_critical_risks": _check_no_open_critical_risks,
    "no_blocked_requests": _check_no_blocked_requests,
    "readiness_scored": _check_readiness_scored,
    "required_evidence_complete": _check_required_evidence_complete,
    "handoff_accepted": _check_handoff_accepted,
}


def gate_check_results(gate: dict, project_id: str, phase_id: str, data: dict, ctx: dict) -> dict[str, bool]:
    """Run a gate's required checks. The result informs the human assessor only."""
    return {c: GATE_CHECKS[c](project_id, phase_id, data, ctx) for c in gate["required_checks"]}


# ---------------------------------------------------------------------------
# Referential integrity


def reference_problems(data: dict[str, list[dict]], profile_ids: set[str]) -> list[str]:
    """Every reference between R1 records resolves, and every child belongs to the same
    project as its parent. Returns a list of orphan descriptions (empty means none)."""
    problems: list[str] = []
    projects = {p["project_id"]: p for p in data["projects"]}
    phases = {p["phase_id"]: p for p in data["phases"]}
    milestones = {m["milestone_id"]: m for m in data["milestones"]}
    tasks = {t["task_id"]: t for t in data["tasks"]}

    def need(kind, rid, table, owner_project=None, where=""):
        if rid not in table:
            problems.append(f"{where}: {kind} {rid} does not exist")
        elif owner_project and table[rid].get("project_id", owner_project) != owner_project:
            problems.append(f"{where}: {kind} {rid} belongs to another project")

    for p in data["projects"]:
        need("phase", p.get("current_phase_id"), phases, p["project_id"], p["project_id"])
        for f in ("complexity_profile_id", "service_profile_id", "segment_profile_id"):
            if p.get(f) not in profile_ids:
                problems.append(f"{p['project_id']}: {f} {p.get(f)} does not exist")
    for kind in ("phases", "milestones", "tasks", "requests", "risks", "issues", "scorecards", "handoffs", "gate_assessments"):
        for row in data.get(kind, []):
            label = str(next(iter(row.values()), kind))
            need("project", row.get("project_id"), projects, None, label)
            if "phase_id" in row and kind != "phases":
                need("phase", row["phase_id"], phases, row.get("project_id"), label)
    for m in data["milestones"]:
        need("phase", m["phase_id"], phases, m["project_id"], m["milestone_id"])
    for t in data["tasks"]:
        if t.get("milestone_id"):
            need("milestone", t["milestone_id"], milestones, t["project_id"], t["task_id"])
        for pred in t.get("predecessor_task_ids") or []:
            need("task", pred, tasks, t["project_id"], t["task_id"])
            if pred == t["task_id"]:
                problems.append(f"{t['task_id']}: lists itself as a predecessor")
    for kind in data:
        for row in data[kind]:
            for key, value in row.items():
                values = value if isinstance(value, list) else [value]
                if key.endswith("_role_id") or key == "role_id":
                    for v in values:
                        if not (isinstance(v, str) and re.fullmatch(r"ROL-[0-9]{6}", v)):
                            problems.append(f"{kind}: {key} {v} is not a registered role ID pattern")
                if key.endswith("person_id"):
                    for v in values:
                        if not (isinstance(v, str) and re.fullmatch(r"PER-[0-9]{6}", v)):
                            problems.append(f"{kind}: {key} {v} is not a registered person ID pattern")
    return problems
