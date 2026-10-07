"""Validator for implementation-tracker-workbook (R3).

Checks that the workbook implements the pinned R1 version without reinterpreting it.
It reads files only; it never publishes, pushes, or changes anything. Workbook
recalculation with a spreadsheet engine is in tools/verify_workbook.py; this validator
runs without one.

Checks (each prints PASS or FAIL):
  R01 required files              R19 request escalation logic
  R02 shared-standard reference   R20 capacity-input inclusion
  R03 R1 source pin               R21 no double counting
  R04 schema-copy hashes          R22 event columns
  R05 synthetic source hashes     R23 JSON payload validity
  R06 JSON Schemas                R24 event schema
  R07 YAML                        R25 CSV export consistency
  R08 workbook structure          R26 JSONL export consistency
  R09 sheet order                 R27 README AI assistance
  R10 table presence              R28 practical workflow
  R11 formula inventory           R29 mandatory labels
  R12 no volatile dates           R30 genericity
  R13 validation lists            R31 no em dashes
  R14 R1 vocabulary parity        R32 private blocklist (when supplied)
  R15 ID patterns                 R33 no secrets
  R16 references                  R34 no external workbook links
  R17 readiness formulas          R35 no macros
  R18 risk formulas               R36 no duplicated R1 authority
                                  R37 configuration consistency
                                  R38 generated documents and expected values current

Private blocklist: --blocklist FILE ... or PORTFOLIO_GATE_BLOCKLIST (os.pathsep-separated),
outside this repository. Matched terms are never printed; only counts are.

Usage:
    python tools/validate.py [--root PATH] [--blocklist FILE ...]
Exit codes: 0 pass, 1 one or more failures.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import re
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import yaml  # noqa: E402
from jsonschema import Draft202012Validator, FormatChecker  # noqa: E402

BLOCKLIST_ENV = "PORTFOLIO_GATE_BLOCKLIST"
EM_DASH = chr(0x2014)
R1_REPO = "implementation-operating-system"
REQUIRED_FILES = (
    "README.md", "LICENSE", "CHANGELOG.md", "CONTRIBUTING.md", "FORMULAS.md", "IMPORT-GUIDE.md", ".gitignore",
    ".github/workflows/validate.yml", "standard/standard-reference.yaml", "workbook/implementation-tracker-workbook.xlsx",
    "docs/architecture.md", "docs/workbook-guide.md", "docs/data-dictionary.md", "docs/starter-mode.md",
    "docs/event-capture-model.md", "docs/export-model.md", "docs/practical-workflow.md", "docs/portfolio-integration.md",
    "schemas/r1/manifest.yaml", "schemas/r3/workbook-metadata.schema.json", "schemas/r3/lookup-entry.schema.json",
    "schemas/r3/capacity-input.schema.json", "config/workbook-settings.yaml", "config/validation-lists.yaml",
    "config/stage-requirements.yaml", "config/event-mappings.yaml", "config/export-map.yaml",
    "data/synthetic/README.md", "data/synthetic/manifest.yaml", "data/synthetic/r1/README.md", "data/synthetic/r3/README.md",
    "data/synthetic/r3/capacity-inputs.csv", "exports/README.md", "exports/jsonl/Event-Log.jsonl",
    "tools/build_workbook.py", "tools/verify_workbook.py", "tools/sync_r1_contracts.py", "tools/validate.py",
    "tools/workbook_spec.py", "tools/reference_model.py",
    "verification/R3-V0.1-CHECKLIST.md", "verification/expected-values.yaml", "verification/formula-audit.md",
    "verification/portability-checklist.md", "verification/referential-integrity.md", "verification/release-gate.md",
)
LABELS = ("proposed design value, not a measured result", "synthetic data", "illustrative example", "user-configurable parameter")
LABEL_VARIANTS = (
    re.compile(r"proposed\s+design\s+value(?!,\s+not\s+a\s+measured\s+result)", re.I),
    re.compile(r"\buser configurable parameter\b", re.I),
    re.compile(r"\billustrative-example\b(?!-[a-z0-9])", re.I),
    re.compile(r"\bsynthetic-data\b(?!-[a-z0-9])", re.I),
)
# Excel and LibreOffice are deliberately not in the list below: a workbook must name the
# spreadsheet applications it targets.
# Vendor and product names that must not appear, stored as SHA-256 hashes of the exact
# name so this public file never spells out the products it guards against. Names of
# one to three words are matched case-sensitively as whole words.
GENERICITY_TERM_HASHES = frozenset({
    "12e5f2025ea19bfe8f8eb2f2219e69af38260f1951f516a35e7390cd81e3f1d9",
    "33a7935db79df2a3bf5ac7ff9f2421015ff61623e005da1cf0cc9e1352c98069",
    "5a06b98b21528d307de51a5b5ab38d9650147fa5c022187dac64956cb5e74d9e",
    "5f5f6ddd5dbf171077a052fe33f2d349f2b3ee91a732c461fb380d801a482d3e",
    "61a463ae2530e7960c35f1ac06b8bf310d3b587de79ef9da386289ed3782089d",
    "73bcfe98830b53a1cabd2fa68c6ba8819adcfb9b0566f7ed5d455582d47973ed",
    "8b9b0b3f792de8a6ad54ee531bd8f2efba7a64189029519237d882b3724dbcfd",
    "a11413b0a4a315c2819e264b40f0ed5161a7b1cd1a2c1726661b7a25575fec6b",
    "b27fb38ba323745c91fe7fd9021605430d43bdb7d3be765266e29364d103e26f",
    "bbc323fb4c8234bba43e21ad21d450c9f059826ac4cbccabe423adaac7cab666",
    "ca96ecb62e7bfb333671f467cd2b0f8dccbc211153e41f6aa7c47ac391c62d6e",
    "dc7620ebfc35d54ef34e32b9eb6f69f1bfe93f294370c2798d91147e34e7ad56",
    "e35c40edf9819dd4f14de7dd4c038d3529312744942e49b7ac63ee165705057c",
    "ff8fdf4e47f0b0957ee901813bc6e5f24d862b6ac4c43d401b3f0f196e40a2b4",
})


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


VENDOR_TOKEN = re.compile(r"[A-Za-z0-9]+(?:\.[A-Za-z0-9]+)*")


def names_listed_vendor(text: str) -> bool:
    """True when any run of one to three words in text, compared case-sensitively, hashes
    to a listed vendor or product name."""
    words = VENDOR_TOKEN.findall(text)
    for n in (1, 2, 3):
        for i in range(len(words) - n + 1):
            if _sha256(" ".join(words[i:i + n])) in GENERICITY_TERM_HASHES:
                return True
    return False
SECRET_PATTERNS = (
    re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{36,}|github_pat_\w{40,})"),
    re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
    re.compile(r"\bsk-(?:ant-)?[A-Za-z0-9_-]{20,}"),
    re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"),
    re.compile(r"\bxox[abposr]-[A-Za-z0-9-]{10,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"(?i)\b(?:api[_-]?key|secret|token|password|passwd)\b[\"']?\s*[:=]\s*[\"'][^\"'\s]{16,}[\"']"),
)
SECRET_FILES = re.compile(r"(?:^|/)(?:\.env(?:\..+)?|id_rsa|id_ed25519|.+\.pem|.+\.key)$")
TEXT_SUFFIXES = {".md", ".yaml", ".yml", ".json", ".jsonl", ".csv", ".py", ".txt", ".toml", ".cfg", ""}
SKIP_DIRS = {".git", "__pycache__", ".venv", "venv", "dist", ".pytest_cache"}
SCAN_EXEMPT = {"tools/validate.py"}
README_SECTIONS = (
    "Purpose", "Who it is for", "What it demonstrates", "Relationship to R1", "Workbook screenshot and visual description",
    "Twelve tabs", "Starter Mode", "Full Mode", "Deterministic formulas", "Readiness", "Capacity Inputs", "Event Log",
    "Synthetic data", "Reproducible build", "Validation", "Practical workflow", "Limitations", "AI assistance",
    "Versioning", "License",
)
WORKFLOW_SECTIONS = ("trigger", "inputs", "steps", "deterministic rules", "outputs", "events", "human decisions",
                     "downstream integrations", "verification", "solo", "early-scale", "structured-growth", "mature")
WORKFLOW_STEPS = ("open workbook", "confirm calculation_as_of_at", "review projects", "update phase", "update tasks",
                  "add or update risk", "process request", "prepare gate evidence", "review readiness",
                  "append or reconcile material events", "review kpi summary", "export capacity inputs",
                  "prepare weekly status", "verify workbook")
AUTHORITY_KEYS = {"phases", "phase_statuses", "gate_outcomes", "transitions", "statuses", "bands", "categories",
                  "events", "gates", "rules", "severities", "stages", "prefixes", "weights", "likelihood_values", "impact_values"}


class Result:
    def __init__(self) -> None:
        self.rows: list[tuple[str, bool, str]] = []

    def add(self, check: str, problems: list[str], ok_note: str) -> None:
        self.rows.append((check, not problems, "; ".join(problems[:8]) if problems else ok_note))

    @property
    def failed(self) -> bool:
        return any(not ok for _, ok, _ in self.rows)


def repo_files(root: Path) -> list[Path]:
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        out += [Path(dirpath, n) for n in filenames]
    return sorted(out)


def rel(root: Path, p: Path) -> str:
    return p.relative_to(root).as_posix()


def text_of(path: Path) -> str | None:
    if path.suffix.lower() == ".xlsx":
        return workbook_text(path)
    if path.suffix.lower() not in TEXT_SUFFIXES:
        return None
    try:
        return path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return None


def workbook_text(path: Path) -> str:
    try:
        with zipfile.ZipFile(path) as z:
            return "\n".join(z.read(n).decode("utf-8", "replace") for n in z.namelist() if n.endswith(".xml"))
    except (zipfile.BadZipFile, OSError):
        return ""


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_blocklist(given, root: Path) -> tuple[list[str], list[str]]:
    names = list(given or [])
    if not names and os.environ.get(BLOCKLIST_ENV):
        names = [p for p in os.environ[BLOCKLIST_ENV].split(os.pathsep) if p]
    terms, problems = [], []
    for name in names:
        path = Path(name).expanduser().resolve()
        if not path.is_file():
            problems.append("blocklist file not found")
            continue
        try:
            path.relative_to(root)
            problems.append("blocklist file must live outside this repository")
            continue
        except ValueError:
            pass
        terms += [ln.strip() for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip() and not ln.strip().startswith("#")]
    return terms, problems


def guard(res: Result, check: str, note: str, fn) -> None:
    try:
        problems, ok = fn()
    except Exception as exc:  # noqa: BLE001
        problems, ok = [f"check could not run: {exc.__class__.__name__}: {exc}"], ""
    res.add(check, problems, ok or note)


def validate(root: Path, blocklist: list[str] | None = None) -> Result:
    import build_workbook as B  # noqa: PLC0415
    import reference_model as RM_  # noqa: PLC0415
    import verify_workbook as V  # noqa: PLC0415
    import workbook_spec as W  # noqa: PLC0415

    # Point the shared modules at the repository being validated (tests use copies).
    W.ROOT = root
    W.PIN = root / "schemas" / "r1"
    W.WORKBOOK_PATH = root / "workbook" / "implementation-tracker-workbook.xlsx"
    W.TABLES.clear()
    res = Result()
    xlsx = W.WORKBOOK_PATH
    cache: dict = {}

    def wb_inputs():
        if "inputs" not in cache:
            cache["inputs"] = V.workbook_inputs(xlsx)
        return cache["inputs"]

    def ctx():
        # The reference evaluation of what the committed workbook holds.
        if "ctx" not in cache:
            cache["ctx"] = RM_.compute(wb_inputs())
        return cache["ctx"]

    # R08 to R14, R34, R35 reuse the workbook verifier's structural checks.
    def structural():
        if "structural" not in cache:
            rep = V.Report()
            V.structural_checks(xlsx, rep)
            cache["structural"] = {row[0][:3]: row for row in rep.rows}
        return cache["structural"]

    def from_structural(code):
        def f():
            row = structural()[code]
            return ([row[2]] if row[1] == "FAIL" else []), row[2]
        return f

    def y(relpath):
        return yaml.safe_load((root / relpath).read_text(encoding="utf-8"))

    # R01
    guard(res, "R01 required files", "", lambda: ([f"missing {f}" for f in REQUIRED_FILES if not (root / f).is_file()], f"{len(REQUIRED_FILES)} present"))

    # R02, R03
    def r02():
        ref = y("standard/standard-reference.yaml")
        problems = [f"missing {k}" for k in ("shared_standard_version", "r1_repo", "r1_commit", "r1_repository_version", "synchronized_at",
                                              "schema_manifest", "configuration_manifest") if k not in ref]
        if str(ref.get("shared_standard_version")) != "1.0.0":
            problems.append("shared_standard_version is not 1.0.0")
        lt = yaml.safe_load((root / "schemas/r1/standard/lifecycle-terms.yaml").read_text(encoding="utf-8"))
        if str(lt.get("standard_version")) != str(ref.get("shared_standard_version")):
            problems.append("pinned standard files do not carry the referenced standard version")
        return problems, f"standard {ref.get('shared_standard_version')}, R1 {ref.get('r1_repository_version')}"
    guard(res, "R02 shared-standard reference", "", r02)

    def r03():
        ref = y("standard/standard-reference.yaml")
        commit = ref.get("r1_commit", "")
        problems = [] if re.fullmatch(r"[0-9a-f]{40}", str(commit)) else ["r1_commit is not a full SHA"]
        for name, value in (("schemas/r1/manifest.yaml", y("schemas/r1/manifest.yaml")["pinned_r1_commit"]),
                            ("data/synthetic/manifest.yaml", y("data/synthetic/manifest.yaml")["pinned_r1_commit"]),
                            ("config/workbook-settings.yaml", y("config/workbook-settings.yaml")["r1_source_commit"]),
                            ("config/validation-lists.yaml", y("config/validation-lists.yaml")["pinned_r1_commit"]),
                            ("config/event-mappings.yaml", y("config/event-mappings.yaml")["pinned_r1_commit"])):
            if value != commit:
                problems.append(f"{name} pins a different R1 commit")
        for entry in y("schemas/r1/manifest.yaml")["files"] + y("data/synthetic/manifest.yaml")["files"]:
            if entry["source_commit"] != commit or entry["authoritative_repo"] != "R1" or entry["source_repo"] != R1_REPO:
                problems.append(f"{entry['local_path']}: source pin differs")
        return problems, f"R1 {commit[:7]} pinned everywhere"
    guard(res, "R03 R1 source pin", "", r03)

    # R04, R05
    def r04():
        man = y("schemas/r1/manifest.yaml")["files"]
        problems = [f"{e['local_path']}: SHA-256 differs from the pinned source" for e in man
                    if not (root / e["local_path"]).is_file() or sha256(root / e["local_path"]) != e["sha256"]]
        listed = {e["local_path"] for e in man}
        extra = [rel(root, p) for p in (root / "schemas/r1").rglob("*") if p.is_file() and rel(root, p) not in listed
                 and rel(root, p) != "schemas/r1/manifest.yaml" and "__pycache__" not in rel(root, p)]
        problems += [f"{e}: unpinned file in schemas/r1" for e in extra]
        return problems, f"{len(man)} pinned contract files match their source hashes"
    guard(res, "R04 schema-copy hashes", "", r04)

    def r05():
        man = y("data/synthetic/manifest.yaml")["files"]
        problems = []
        for e in man:
            p = root / e["local_path"]
            if not p.is_file() or sha256(p) != e["sha256"]:
                problems.append(f"{e['local_path']}: SHA-256 differs from the pinned R1 source")
                continue
            lines = [ln for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]
            n = len(lines) - 1 if p.suffix == ".csv" else len(lines)
            if n != e["row_count"]:
                problems.append(f"{e['local_path']}: row count {n}, manifest {e['row_count']}")
        row = structural()["W10"]
        if row[1] == "FAIL":
            problems.append(row[2])
        counts = ", ".join(f"{Path(e['local_path']).stem} {e['row_count']}" for e in man)
        return problems, counts + "; workbook inputs equal the pinned sources"
    guard(res, "R05 synthetic source hashes", "", r05)

    # R06, R07
    def r06():
        problems, n = [], 0
        for p in sorted(list((root / "schemas").rglob("*.json"))):
            doc = json.loads(p.read_text(encoding="utf-8"))
            Draft202012Validator.check_schema(doc)
            n += 1
            v = Draft202012Validator(doc, format_checker=FormatChecker())
            for i, ex in enumerate(doc.get("examples", [])):
                errs = list(v.iter_errors(ex))
                if errs:
                    problems.append(f"{rel(root, p)} example {i}: {errs[0].message}")
        return problems, f"{n} schemas valid; every example validates"
    guard(res, "R06 JSON Schemas", "", r06)

    def r07():
        problems, n = [], 0
        for p in repo_files(root):
            if p.suffix in (".yaml", ".yml"):
                n += 1
                try:
                    yaml.safe_load(p.read_text(encoding="utf-8"))
                except yaml.YAMLError as exc:
                    problems.append(f"{rel(root, p)}: {exc.__class__.__name__}")
        return problems, f"{n} YAML files parse"
    guard(res, "R07 YAML", "", r07)

    guard(res, "R08 workbook structure (no hidden sheets)", "", from_structural("W02"))
    guard(res, "R09 sheet order", "", from_structural("W01"))
    guard(res, "R10 table presence", "", from_structural("W03"))

    def r11():
        problems = []
        row = structural()["W04"]
        if row[1] == "FAIL":
            problems.append(row[2])
        formulas = (root / "FORMULAS.md").read_text(encoding="utf-8")
        for spec in W.tables().values():
            for c in spec.columns:
                if c.kind == "formula" and c.excel is not None and f"`{spec.name}[{c.name}]`" not in formulas:
                    problems.append(f"FORMULAS.md does not document {spec.name}[{c.name}]")
        for key, *_ in W.KPI_ROWS:
            if f"`{key}`" not in formulas:
                problems.append(f"FORMULAS.md does not document KPI {key}")
        return problems, row[2] + "; every formula documented in FORMULAS.md"
    guard(res, "R11 formula inventory", "", r11)
    guard(res, "R12 no volatile dates", "", from_structural("W07"))

    def r13():
        problems = []
        vl = y("config/validation-lists.yaml")["lists"]
        by_type = {item["lookup_type"]: item for item in vl}
        for src in W.LOOKUP_SOURCES:
            item = by_type.get(src.lookup_type)
            if not item:
                problems.append(f"validation-lists.yaml lacks {src.lookup_type}")
                continue
            if item["values"] != [k for k, _ in src.extract()]:
                problems.append(f"{src.lookup_type}: list drifted from {src.source_path}")
            if item["source_path"] != src.source_path or item["source_repo"] != src.source_repo:
                problems.append(f"{src.lookup_type}: source citation differs")
        problems += [f"validation-lists.yaml has unknown list {t}" for t in by_type if t not in {s.lookup_type for s in W.LOOKUP_SOURCES}]
        row = structural()["W08"]
        if row[1] == "FAIL":
            problems.append(row[2])
        return problems, f"{len(vl)} lists cite their source and match it; workbook lists match"
    guard(res, "R13 validation lists", "", r13)

    def r14():
        problems = []
        lt = W.load_yaml("standard/lifecycle-terms.yaml")
        entries = W.lookup_entries()
        checks = {
            "phase_key": [p["phase_key"] for p in lt["phases"]], "phase_status": lt["phase_statuses"], "gate_outcome": lt["gate_outcomes"],
            "request_status": W.load_yaml("config/request-state-machine.yaml")["statuses"],
            "severity": [s["severity_id"] for s in W.load_yaml("standard/severity-scale.yaml")["severities"]],
            "readiness_category": [c["category_id"] for c in W.load_yaml("standard/readiness-categories.yaml")["categories"]],
            "org_stage": [s["stage_id"] for s in W.load_yaml("standard/org-stages.yaml")["stages"]],
            "project_status": W.schema_for("project")["properties"]["project_status"]["enum"],
        }
        for t, want in checks.items():
            if W.lookup_values(entries, t) != want:
                problems.append(f"{t} differs from R1")
        if [w["category"] for w in W.readiness_weights()] != checks["readiness_category"]:
            problems.append("readiness weight categories differ from the R1 categories")
        # Every value the workbook holds in an R1 vocabulary field must be an R1 value.
        catalog = {e["event_type"]: e for e in W.load_yaml("standard/event-catalog.yaml")["events"]}
        for name, rows in wb_inputs().items():
            spec = W.tables()[name]
            if spec.owner != "R1":
                continue
            if spec.entity == "event":
                for r in rows:
                    entry = catalog.get(r.get("event_type"))
                    if not entry or entry.get("scenario_pack") or entry["producer_repo"] != R1_REPO:
                        problems.append(f"{name} {r.get('event_id')}: event type {r.get('event_type')} is not a registered R1 core event")
                continue
            schema = W.schema_for(spec.entity)
            props = dict(schema["properties"])
            props.update(schema["properties"].get("categories", {}).get("items", {}).get("properties", {}))
            for r in rows:
                for k, v in r.items():
                    enum = props.get(k, {}).get("enum")
                    if enum and v not in enum:
                        problems.append(f"{name} {r.get(spec.id_column)}: {k} {v!r} is not an R1 value")
        return problems, "R1 vocabularies equal the pin; every workbook vocabulary value is an R1 value"
    guard(res, "R14 R1 vocabulary parity", "", r14)

    def r15():
        registry = W.load_yaml("standard/id-registry.yaml")
        active = {p["prefix"] for p in registry["prefixes"] if p["status"] == "active"}
        problems, n = [], 0
        c = ctx()
        for name, rows in c.items():
            if not isinstance(rows, list):
                continue
            for r in rows:
                for k, v in r.items():
                    values = v if isinstance(v, list) else [v]
                    if k == "gate_id" or not (k.endswith("_id") or k.endswith("_ids") or k.endswith("_refs")):
                        # gate_id is an R1 gate configuration key such as launch_gate, not a record ID.
                        continue
                    for x in values:
                        if not isinstance(x, str) or x in ("", "source_not_found", "phase_not_found", "scorecard_not_found"):
                            continue
                        n += 1
                        if not re.fullmatch(r"[A-Z]{3}-[0-9]{6}", x) or x[:3] not in active:
                            problems.append(f"{name}.{k}: {x} is not a registered TYPE-NNNNNN ID")
        return problems, f"{n} ID values use registered TYPE-NNNNNN prefixes"
    guard(res, "R15 ID patterns", "", r15)

    def r16():
        c = ctx()
        r1 = W.r1_rules()
        data = {"projects": c["tblProjects"], "phases": c["tblPhases"], "milestones": c["tblMilestones"], "tasks": c["tblTasks"],
                "requests": c["tblRequests"], "risks": c["tblRisks"], "issues": c["tblIssues"],
                "gate_assessments": c["tblGateAssessments"], "handoffs": c["tblHandoffs"]}
        profiles = set(W.lookup_values(c["tblLookupEntries"], "profile_id"))
        problems = list(r1.reference_problems(data, profiles))
        kpi = {r["kpi_key"]: r["value"] for r in c["tblKpiSummary"]}
        if kpi["reference_problem_count"]:
            problems.append(f"{kpi['reference_problem_count']} records fail reference_check")
        problems += [f"event {e['event_id']}: subject missing" for e in c["tblEventLog"] if e["subject_check"] == "missing"]
        problems += [f"capacity {r['capacity_input_id']}: source or component missing" for r in c["tblCapacityInputs"]
                     if r["project_id"] == "source_not_found" or r["planned_hours"] == "component_not_found"]
        return problems, "0 orphans (R1 reference rule, workbook reference checks, event subjects, capacity sources)"
    guard(res, "R16 references", "", r16)

    def r17():
        c = ctx()
        r1 = W.r1_rules()
        rw = W.load_yaml("config/readiness-weights.yaml")
        problems = []
        for card in c["tblReadinessSummary"]:
            entries = {r["category"]: r for r in c["tblReadiness"] if r["readiness_scorecard_id"] == card["readiness_scorecard_id"]}
            want = r1.readiness_scorecard(entries, rw)
            if abs(float(want["overall_score"]) - card["overall_score"]) > 1e-9 or want["incomplete_required_evidence_flag"] != card["incomplete_required_evidence_flag"]:
                problems.append(f"{card['readiness_scorecard_id']}: workbook result differs from R1")
        spec = W.tables()["tblReadiness"]
        for name in ("weight", "achieved_rate", "category_score", "overall_score", "incomplete_required_evidence_flag"):
            f = W.formula_for(spec, spec.column(name))
            literals = set(re.findall(r"(?<![A-Za-z_\d.])\d+(?:\.\d+)?(?![\d])", re.sub(r'"[^"]*"', "", f)))
            if literals - {"0", "1", "2", "100"}:
                problems.append(f"{name}: hardcoded number(s) {sorted(literals)}; weights must come from the R1 mirror")
        if "tblReadinessWeights[weight]" not in W.formula_for(spec, spec.column("weight")):
            problems.append("weight does not read the R1 weight mirror")
        return problems, f"{len(c['tblReadinessSummary'])} scorecards equal R1 readiness_scorecard; no hardcoded weights"
    guard(res, "R17 readiness formulas", "", r17)

    def r18():
        c = ctx()
        r1 = W.r1_rules()
        rr = W.load_yaml("config/risk-rules.yaml")
        problems = []
        for r in c["tblRisks"]:
            want = r1.risk_score(r["likelihood"], r["impact"], rr)
            if r["risk_score"] != want or r["risk_band"] != r1.risk_band(want, rr)["band"]:
                problems.append(f"{r['risk_id']}: workbook score or band differs from R1")
        f = W.formula_for(W.tables()["tblRisks"], W.tables()["tblRisks"].column("risk_score"))
        if "*" not in f or "risk_likelihood_max" not in f:
            problems.append("risk_score formula is not likelihood x impact on the R1 scale")
        return problems, f"{len(c['tblRisks'])} risk scores and bands equal R1 risk_score and risk_band"
    guard(res, "R18 risk formulas", "", r18)

    def r19():
        c = ctx()
        r1 = W.r1_rules()
        sla = W.load_yaml("config/sla-rules.yaml")
        problems = []
        for r in c["tblRequests"]:
            want = r1.expected_escalation_due_at(r, sla) or ""
            if (r.get("escalation_due_at") or "") != want or r["escalation_due_check"] != "consistent":
                problems.append(f"{r['request_id']}: escalation differs from R1 config/sla-rules.yaml")
        return problems, f"{len(c['tblRequests'])} requests: escalation_due_at equals the R1 rule"
    guard(res, "R19 request escalation logic", "", r19)

    def r20():
        schema = json.loads((root / "schemas/r3/capacity-input.schema.json").read_text(encoding="utf-8"))
        v = Draft202012Validator(schema, format_checker=FormatChecker())
        problems = []
        rows = read_csv(root / "exports/csv/capacity-inputs.csv", schema)
        for r in rows:
            errs = list(v.iter_errors(r))
            if errs:
                problems.append(f"{r.get('capacity_input_id')}: {errs[0].message}")
        return problems, f"{len(rows)} exported capacity inputs validate (authoritative, informational, excluded methods only)"
    guard(res, "R20 capacity-input inclusion", "", r20)

    def r21():
        c = ctx()
        cap = {r["check_key"]: r["value"] for r in c["tblCapacitySummary"]}
        problems = []
        auth = [r["workload_component_id"] for r in c["tblCapacityInputs"] if r["capacity_inclusion_method"] == "authoritative_workload"]
        problems += [f"component {x} authoritative more than once" for x in sorted({x for x in auth if auth.count(x) > 1})]
        if cap["hours_reconciliation"] != "reconciled":
            problems.append("authoritative hours do not equal task hours")
        if cap["tasks_without_authoritative_row"] or cap["duplicate_authoritative_count"]:
            problems.append("a task lacks an authoritative row or a duplicate exists")
        return problems, f"each component authoritative once; {cap['authoritative_planned_hours_total']} planned hours counted once"
    guard(res, "R21 no double counting", "", r21)

    def r22():
        schema = W.load_json("standard/schemas/event.schema.json")
        cols = [c.name for c in W.tables()["tblEventLog"].columns[:10]]
        problems = [] if cols == schema["required"] else ["Event Log columns differ from the ten shared event-contract fields"]
        with (root / "exports/csv/event-log.csv").open(encoding="utf-8", newline="") as h:
            header = next(csv.reader(h))
        if header != schema["required"]:
            problems.append("event-log.csv header differs from the event contract")
        return problems, "10 event-contract columns in order"
    guard(res, "R22 event columns", "", r22)

    def r23():
        problems = []
        with (root / "exports/csv/event-log.csv").open(encoding="utf-8", newline="") as h:
            for r in csv.DictReader(h):
                try:
                    if not isinstance(json.loads(r["payload"]), dict):
                        problems.append(f"{r['event_id']}: payload is not a JSON object")
                except json.JSONDecodeError:
                    problems.append(f"{r['event_id']}: payload is not valid JSON")
        for e in wb_inputs()["tblEventLog"]:
            try:
                json.loads(e["payload"])
            except json.JSONDecodeError:
                problems.append(f"{e['event_id']}: workbook payload is not valid JSON")
        return problems, "every payload cell is a valid JSON object"
    guard(res, "R23 JSON payload validity", "", r23)

    def r24():
        schema = W.load_json("standard/schemas/event.schema.json")
        catalog = {e["event_type"]: e for e in W.load_yaml("standard/event-catalog.yaml")["events"]}
        v = Draft202012Validator(schema, format_checker=FormatChecker())
        problems, n = [], 0
        for line in (root / "exports/jsonl/Event-Log.jsonl").read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            n += 1
            e = json.loads(line)
            errs = list(v.iter_errors(e))
            if errs:
                problems.append(f"{e.get('event_id')}: {errs[0].message}")
            entry = catalog.get(e.get("event_type"))
            if not entry or entry.get("scenario_pack") or entry["producer_repo"] != e.get("source_repo"):
                problems.append(f"{e.get('event_id')}: not a registered R1 core event from its producer")
            elif any(f not in e["payload"] for f in entry["required_payload_fields"]):
                problems.append(f"{e.get('event_id')}: payload misses a required field")
        problems += [f"{e['event_id']}: {e['event_type_check']}" for e in ctx()["tblEventLog"] if e["event_type_check"] != "registered"]
        return problems, f"{n} events validate against the shared event schema and catalog"
    guard(res, "R24 event schema", "", r24)

    def r25():
        export_map = y("config/export-map.yaml")["exports"]
        problems, n = [], 0
        specs = W.tables()
        for item in export_map:
            spec = specs[item["table"]]
            want_cols = [c.name for c in spec.columns[:10]] if spec.name == "tblEventLog" else [c.name for c in spec.columns if c.export and c.kind in ("input", "formula")]
            if item["columns"] != want_cols:
                problems.append(f"{item['file']}: export-map columns differ from the workbook specification")
            if spec.owner == "R1" and spec.name not in ("tblEventLog",) and spec.entity not in ("gate-assessment", "handoff"):
                if item["columns"] != W.schema_for(spec.entity)["x-csv-columns"]:
                    problems.append(f"{item['file']}: columns differ from the R1 CSV contract")
            if not item["file"].endswith(".csv"):
                continue
            n += 1
            with (root / item["file"]).open(encoding="utf-8", newline="") as h:
                reader = csv.reader(h)
                header = next(reader)
                rows = list(reader)
            if header != item["columns"]:
                problems.append(f"{item['file']}: header differs from config/export-map.yaml")
            expected_rows = len(ctx()[item["table"]])
            if len(rows) != expected_rows:
                problems.append(f"{item['file']}: {len(rows)} rows, workbook table has {expected_rows}")
        same_as_r1 = 0
        for e in y("data/synthetic/manifest.yaml")["files"]:
            name = Path(e["local_path"]).name
            if name == "events.jsonl":
                continue
            if (root / "exports/csv" / name).read_bytes() != (root / e["local_path"]).read_bytes():
                problems.append(f"exports/csv/{name} is not byte-identical to the pinned R1 file")
            else:
                same_as_r1 += 1
        return problems, f"{n} CSV exports match the export map; {same_as_r1} R1 entity exports byte-identical to pinned R1"
    guard(res, "R25 CSV export consistency", "", r25)

    def r26():
        problems = []
        jsonl = [json.loads(ln) for ln in (root / "exports/jsonl/Event-Log.jsonl").read_text(encoding="utf-8").splitlines() if ln.strip()]
        with (root / "exports/csv/event-log.csv").open(encoding="utf-8", newline="") as h:
            rows = list(csv.DictReader(h))
        if len(jsonl) != len(rows):
            problems.append("JSONL and CSV event exports differ in length")
        for a, b in zip(jsonl, rows):
            if a["event_id"] != b["event_id"] or a["payload"] != json.loads(b["payload"]):
                problems.append(f"{a['event_id']}: JSONL and CSV exports differ")
        if (root / "exports/jsonl/Event-Log.jsonl").read_bytes() != (root / "data/synthetic/r1/events.jsonl").read_bytes():
            problems.append("Event-Log.jsonl is not byte-identical to the pinned R1 events.jsonl")
        return problems, f"{len(jsonl)} events; JSONL equals CSV and is byte-identical to pinned R1"
    guard(res, "R26 JSONL export consistency", "", r26)

    def r27():
        text = (root / "README.md").read_text(encoding="utf-8")
        heads = [h.strip() for h in re.findall(r"^##\s+(.+)$", text, re.MULTILINE)]
        problems = [] if [h.lower() for h in heads] == [s.lower() for s in README_SECTIONS] else ["README.md sections differ from the required 20 in order"]
        ai = text.split("## AI assistance", 1)[-1].split("\n## ", 1)[0].lower() if "## AI assistance" in text else ""
        for phrase in ("documentation", "implementation", "testing", "reviewed", "approved", "deterministic"):
            if phrase not in ai:
                problems.append(f"AI assistance section does not mention {phrase}")
        for claim in ("reference implementation", "not been historically deployed", "not customer data"):
            if claim not in text:
                problems.append(f"README does not state: {claim}")
        if "docs/practical-workflow.md" not in text:
            problems.append("README does not link docs/practical-workflow.md")
        return problems, "20 sections; AI assistance disclosed; reference-implementation statements present"
    guard(res, "R27 README AI assistance", "", r27)

    def r28():
        wf = (root / "docs/practical-workflow.md").read_text(encoding="utf-8")
        heads = [re.sub(r"[^a-z0-9 _-]", "", h.strip().lower()) for h in re.findall(r"^#{2,4}\s+(.+)$", wf, re.MULTILINE)]
        problems = [f"missing section {s}" for s in WORKFLOW_SECTIONS if not any(s in h for h in heads)]
        problems += [f"missing step: {s}" for s in WORKFLOW_STEPS if not any(s in h for h in heads)]
        if "Synthetic Project A" not in wf:
            problems.append("workflow does not follow Synthetic Project A")
        for part in ("Tab used", "User action", "Formula or rule", "Authoritative source", "Event implications", "Downstream consumer"):
            if wf.count(part) < len(WORKFLOW_STEPS):
                problems.append(f"not every step shows {part}")
        return problems, "13 required sections and 14 steps, each with tab, action, rule, source, events, consumer"
    guard(res, "R28 practical workflow", "", r28)

    def r29():
        problems = []
        for readme in ("data/synthetic/README.md", "data/synthetic/r1/README.md", "data/synthetic/r3/README.md", "exports/README.md"):
            if LABELS[1] not in (root / readme).read_text(encoding="utf-8").lower():
                problems.append(f"{readme} lacks the synthetic data label")
        wb_text = workbook_text(root / "workbook/implementation-tracker-workbook.xlsx")
        for label in (LABELS[1], LABELS[2], LABELS[3]):
            if label not in wb_text:
                problems.append(f"workbook README tab lacks '{label}'")
        settings_text = (root / "config/workbook-settings.yaml").read_text(encoding="utf-8")
        if LABELS[3] not in settings_text:
            problems.append("workbook-settings.yaml does not mark configurable parameters")
        if LABELS[3] not in (root / "config/stage-requirements.yaml").read_text(encoding="utf-8"):
            problems.append("stage-requirements.yaml does not mark configurable parameters")
        for p in repo_files(root):
            r = rel(root, p)
            if r in SCAN_EXEMPT or r.startswith(("tests/", "schemas/r1/")):
                continue
            t = text_of(p)
            if t and any(pat.search(t) for pat in LABEL_VARIANTS):
                problems.append(f"{r}: label near-variant")
        return problems, "synthetic data, illustrative example, and user-configurable parameter labels present; no near-variants"
    guard(res, "R29 mandatory labels", "", r29)

    def scan(patterns, skip_pin=False):
        hits = []
        for p in repo_files(root):
            r = rel(root, p)
            if r in SCAN_EXEMPT or r.startswith("tests/") or (skip_pin and r.startswith("schemas/r1/")):
                continue
            t = text_of(p)
            if t and any(pat.search(t) for pat in patterns):
                hits.append(r)
        return hits

    def vendor_hits():
        hits = []
        for p in repo_files(root):
            r = rel(root, p)
            if r in SCAN_EXEMPT or r.startswith("tests/"):
                continue
            t = text_of(p)
            if t and names_listed_vendor(t):
                hits.append(r)
        return hits

    guard(res, "R30 genericity", "", lambda: (
        [f"{h}: names a listed vendor or product" for h in vendor_hits()],
        f"no listed vendor or product names ({len(GENERICITY_TERM_HASHES)} checked)"))

    def r31():
        hits = []
        for p in repo_files(root):
            t = text_of(p)
            if t and EM_DASH in t:
                hits.append(rel(root, p))
        return [f"em dash in {h}" for h in hits], "0 em dashes (text files and workbook XML)"
    guard(res, "R31 no em dashes", "", r31)

    def r32():
        terms, probs = load_blocklist(blocklist, root)
        if probs:
            return probs, ""
        if not terms:
            return [], "no private blocklist supplied; check skipped (supply one before publication)"
        pats = [re.compile(r"(?<![A-Za-z0-9])" + re.escape(t) + r"(?![A-Za-z0-9])", re.I) for t in terms]
        hits = scan(pats) + [rel(root, p) for p in repo_files(root) if any(pt.search(rel(root, p)) for pt in pats)]
        return ([f"{len(set(hits))} file(s) contain a private term"] if hits else []), f"{len(terms)} private terms loaded; 0 hits"
    guard(res, "R32 private blocklist", "", r32)

    def r33():
        problems = [f"{rel(root, p)}: secret-bearing file name" for p in repo_files(root) if SECRET_FILES.search(rel(root, p))]
        problems += [f"{h}: credential pattern" for h in scan(SECRET_PATTERNS)]
        return problems, "none"
    guard(res, "R33 no secrets", "", r33)
    guard(res, "R34 no external workbook links", "", from_structural("W06"))
    guard(res, "R35 no macros", "", from_structural("W05"))

    def r36():
        problems = []
        allowed = {"config/validation-lists.yaml", "config/export-map.yaml", "config/event-mappings.yaml",
                   "config/stage-requirements.yaml", "config/workbook-settings.yaml", "verification/expected-values.yaml"}
        for p in repo_files(root):
            r = rel(root, p)
            if r.startswith(("schemas/r1/", "tests/")) or p.suffix not in (".yaml", ".yml"):
                continue
            doc = yaml.safe_load(p.read_text(encoding="utf-8"))
            keys = set(doc) if isinstance(doc, dict) else set()
            if r not in allowed and keys & AUTHORITY_KEYS:
                problems.append(f"{r}: defines {sorted(keys & AUTHORITY_KEYS)}, which R1 owns")
            if r in allowed and r != "verification/expected-values.yaml" and keys & AUTHORITY_KEYS:
                problems.append(f"{r}: carries an R1 definition key {sorted(keys & AUTHORITY_KEYS)}")
        for p in (root / "schemas/r3").glob("*.json"):
            props = json.loads(p.read_text(encoding="utf-8"))["properties"]
            for bad in ("status", "phase_status", "outcome", "severity", "risk_score", "weight"):
                if bad in props:
                    problems.append(f"{rel(root, p)}: R3 schema redefines {bad}")
        return problems, "no R3 lifecycle, readiness category, risk rule, request state machine, or event catalog; synchronized copies cite R1"
    guard(res, "R36 no duplicated R1 authority", "", r36)

    def r37():
        problems = []
        st = y("config/workbook-settings.yaml")
        meta = {"workbook_id": st["workbook_id"], "workbook_version": str(st["workbook_version"]), "r1_commit": st["r1_source_commit"],
                "shared_standard_version": str(st["shared_standard_version"]), "calculation_as_of_at": st["calculation_as_of_at"],
                "event_reconciliation_from_at": st["event_reconciliation_from_at"], "org_stage": st["selected_org_stage"],
                "operating_mode": st["default_operating_mode"], "generated_at": st["generated_at"]}
        schema = json.loads((root / "schemas/r3/workbook-metadata.schema.json").read_text(encoding="utf-8"))
        problems += [f"workbook-settings: {e.message}" for e in Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(meta)]
        sr = y("config/stage-requirements.yaml")
        stages = [s["stage_id"] for s in W.load_yaml("standard/org-stages.yaml")["stages"]]
        specs = W.tables()
        for item in sr["fields"] + sr["controls"]:
            name = item.get("field") or item.get("control")
            for stg in stages:
                if item.get(stg) not in sr["levels"]:
                    problems.append(f"stage-requirements {name}: {stg} is not required, recommended, or optional")
            if "field" in item:
                table, column = item["field"].split(".")
                if table not in specs or column not in [c.name for c in specs[table].columns]:
                    problems.append(f"stage-requirements: {item['field']} is not a workbook column")
                elif specs[table].column(column).required and any(item[s] != "required" for s in stages):
                    problems.append(f"stage-requirements: {item['field']} is R1-required and cannot be relaxed")
        catalog = {e["event_type"]: e for e in W.load_yaml("standard/event-catalog.yaml")["events"]}
        for m in y("config/event-mappings.yaml")["mappings"]:
            entry = catalog.get(m["event_type"])
            if not entry or entry.get("scenario_pack") or entry["producer_repo"] != R1_REPO:
                problems.append(f"event-mappings: {m['event_type']} is not an R1 core event")
                continue
            if m["subject_type"] != entry["subject_type"]:
                problems.append(f"event-mappings: {m['event_type']} subject type differs from the catalog")
            missing = set(entry["required_payload_fields"]) - set(m["required_payload_source_fields"])
            if missing:
                problems.append(f"event-mappings: {m['event_type']} lacks payload sources {sorted(missing)}")
            extra = set(m["optional_payload_source_fields"]) - set(entry["optional_payload_fields"])
            if extra:
                problems.append(f"event-mappings: {m['event_type']} maps unknown payload fields {sorted(extra)}")
            if m["source_table"] not in specs:
                problems.append(f"event-mappings: {m['source_table']} is not a workbook table")
        return problems, "settings, stage requirements, and event mappings consistent with R1 and the workbook"
    guard(res, "R37 configuration consistency", "", r37)

    def r38():
        problems = []
        c = ctx()
        expected = yaml.safe_load((root / "verification/expected-values.yaml").read_text(encoding="utf-8"))
        if expected != json.loads(json.dumps(RM_.expected_values(c))):
            problems.append("verification/expected-values.yaml is stale")
        formulas = (root / "FORMULAS.md").read_text(encoding="utf-8")
        marker = "<!-- GENERATED FORMULA INVENTORY BELOW -->\n\n"
        if marker not in formulas or formulas.split(marker, 1)[1] != B.formulas_markdown(c):
            problems.append("FORMULAS.md inventory is stale (run tools/build_workbook.py --docs)")
        dd = (root / "docs/data-dictionary.md").read_text(encoding="utf-8")
        marker2 = "<!-- GENERATED DATA DICTIONARY BELOW -->\n\n"
        if marker2 not in dd or dd.split(marker2, 1)[1] != B.data_dictionary_markdown():
            problems.append("docs/data-dictionary.md is stale (run tools/build_workbook.py --docs)")
        return problems, "expected values, formula inventory, and data dictionary match the specification"
    guard(res, "R38 generated documents and expected values current", "", r38)

    res.rows.sort(key=lambda r: r[0])
    return res


def read_csv(path: Path, schema: dict) -> list[dict]:
    props = schema["properties"]
    out = []
    with path.open(encoding="utf-8", newline="") as h:
        for raw in csv.DictReader(h):
            rec = {}
            for k, v in raw.items():
                t = props.get(k, {}).get("type", "string")
                if v == "":
                    continue
                if t == "number":
                    rec[k] = float(v) if "." in v else int(v)
                elif t == "boolean":
                    rec[k] = v == "true" if v in ("true", "false") else v
                else:
                    rec[k] = v
            out.append(rec)
    return out


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    parser = argparse.ArgumentParser(description="Validate the tracker workbook repository.")
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--blocklist", nargs="*")
    args = parser.parse_args(argv)
    res = validate(Path(args.root).resolve(), args.blocklist)
    for check, ok, note in res.rows:
        print(f"{'PASS' if ok else 'FAIL'} {check}: {note}")
    failed = sum(1 for _, ok, _ in res.rows if not ok)
    print(f"RESULT: {'FAIL' if failed else 'PASS'} ({len(res.rows) - failed} passed, {failed} failed)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
