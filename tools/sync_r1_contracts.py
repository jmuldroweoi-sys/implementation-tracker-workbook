"""Synchronize the version-pinned R1 contracts and synthetic inputs into this repository.

R1 (implementation-operating-system) is the authority for every vocabulary, schema,
rule, and synthetic record that the workbook implements. This tool copies the exact
bytes of the files R3 needs from ONE deliberately specified R1 commit, writes a SHA-256
manifest, and updates the pin in standard/standard-reference.yaml.

It never reads "latest": the commit is a required argument, and every file is read
with `git show <commit>:<path>`, so uncommitted R1 changes can never leak in.

Usage:
    python tools/sync_r1_contracts.py --r1-repo PATH --r1-commit FULL_SHA [--synchronized-at ISO_UTC]

After a sync, rebuild the workbook, regenerate exports and expected values, and run
every check: R3 must be revalidated against the new pin.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
R1_REPO_NAME = "implementation-operating-system"
R3_REPO_NAME = "implementation-tracker-workbook"

# Contracts R3 needs, by their path in R1. Copied to schemas/r1/<same path>.
# data/synthetic/README.md is pinned for its role table (role IDs and role keys).
CONTRACT_FILES = (
    "standard/id-registry.yaml",
    "standard/event-catalog.yaml",
    "standard/lifecycle-terms.yaml",
    "standard/severity-scale.yaml",
    "standard/readiness-categories.yaml",
    "standard/org-stages.yaml",
    "standard/status-vocabularies.yaml",
    "standard/label-rules.yaml",
    "standard/schemas/event.schema.json",
    "schemas/project.schema.json",
    "schemas/phase.schema.json",
    "schemas/milestone.schema.json",
    "schemas/task.schema.json",
    "schemas/gate-assessment.schema.json",
    "schemas/request.schema.json",
    "schemas/handoff.schema.json",
    "schemas/risk.schema.json",
    "schemas/issue.schema.json",
    "schemas/readiness-scorecard.schema.json",
    "lifecycle/lifecycle.yaml",
    "lifecycle/gates.yaml",
    "config/request-state-machine.yaml",
    "config/sla-rules.yaml",
    "config/risk-rules.yaml",
    "config/lead-time-rules.yaml",
    "config/readiness-weights.yaml",
    "profiles/profile.schema.json",
    "profiles/examples/org-stage-startup.yaml",
    "profiles/examples/complexity-tier-standard.yaml",
    "profiles/examples/service-tier-standard.yaml",
    "profiles/examples/segment-mid-market.yaml",
    "tools/r1_rules.py",
    "data/synthetic/README.md",
)
# R1 synthetic inputs. Copied to data/synthetic/r1/<file name>.
SYNTHETIC_FILES = (
    "data/synthetic/projects.csv",
    "data/synthetic/phases.csv",
    "data/synthetic/milestones.csv",
    "data/synthetic/tasks.csv",
    "data/synthetic/requests.csv",
    "data/synthetic/risks.csv",
    "data/synthetic/issues.csv",
    "data/synthetic/readiness.csv",
    "data/synthetic/events.jsonl",
)
CONTRACT_DIR = "schemas/r1"
SYNTHETIC_DIR = "data/synthetic/r1"


def git(repo: Path, *args: str) -> bytes:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, check=True).stdout


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def row_count(path: str, data: bytes) -> int:
    lines = [ln for ln in data.decode("utf-8").splitlines() if ln.strip()]
    return len(lines) - 1 if path.endswith(".csv") else len(lines)


def repository_version(changelog: bytes) -> str:
    match = re.search(r"^## \[(\d+\.\d+\.\d+)\]", changelog.decode("utf-8"), re.MULTILINE)
    if not match:
        raise SystemExit("could not read the R1 repository version from CHANGELOG.md")
    return match.group(1)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--r1-repo", required=True, help="Path to a local clone of implementation-operating-system")
    parser.add_argument("--r1-commit", required=True, help="Full 40-character R1 commit SHA to pin")
    parser.add_argument("--synchronized-at", default=None, help="UTC timestamp to record (default: the R1 commit time)")
    args = parser.parse_args(argv)

    if not re.fullmatch(r"[0-9a-f]{40}", args.r1_commit):
        raise SystemExit("--r1-commit must be a full 40-character SHA; branch names and 'latest' are refused")
    repo = Path(args.r1_repo).resolve()
    resolved = git(repo, "rev-parse", "--verify", f"{args.r1_commit}^{{commit}}").decode().strip()
    if resolved != args.r1_commit:
        raise SystemExit("the R1 commit does not resolve to itself")
    synced_at = args.synchronized_at or git(repo, "show", "-s", "--format=%cI", args.r1_commit).decode().strip()
    if not synced_at.endswith("Z"):
        # Normalize the commit time to UTC with Z.
        from datetime import datetime, timezone

        synced_at = datetime.fromisoformat(synced_at).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    standard_version = None
    contract_entries, synthetic_entries = [], []
    for src in CONTRACT_FILES:
        data = git(repo, "show", f"{args.r1_commit}:{src}")
        local = f"{CONTRACT_DIR}/{src}"
        (ROOT / local).parent.mkdir(parents=True, exist_ok=True)
        (ROOT / local).write_bytes(data)
        if src == "standard/lifecycle-terms.yaml":
            standard_version = str(yaml.safe_load(data)["standard_version"])
        contract_entries.append({
            "source_repo": R1_REPO_NAME, "source_commit": args.r1_commit, "source_path": src,
            "local_path": local, "sha256": sha256(data), "authoritative_repo": "R1",
        })
    for src in SYNTHETIC_FILES:
        data = git(repo, "show", f"{args.r1_commit}:{src}")
        local = f"{SYNTHETIC_DIR}/{Path(src).name}"
        (ROOT / local).parent.mkdir(parents=True, exist_ok=True)
        (ROOT / local).write_bytes(data)
        synthetic_entries.append({
            "source_repo": R1_REPO_NAME, "source_commit": args.r1_commit, "source_path": src,
            "local_path": local, "sha256": sha256(data), "row_count": row_count(src, data),
            "authoritative_repo": "R1",
        })

    header = (
        "# Generated by tools/sync_r1_contracts.py. Do not edit by hand.\n"
        "# Each file below is a byte-identical copy of an R1 file at the pinned commit.\n"
        "# tools/validate.py fails if a local copy's SHA-256 differs from this manifest.\n"
    )
    (ROOT / CONTRACT_DIR / "manifest.yaml").write_text(
        header + yaml.safe_dump({"pinned_r1_commit": args.r1_commit, "files": contract_entries}, sort_keys=False, width=200),
        encoding="utf-8")
    (ROOT / "data/synthetic/manifest.yaml").write_text(
        header.replace("an R1 file", "an R1 synthetic data file")
        + yaml.safe_dump({"pinned_r1_commit": args.r1_commit, "files": synthetic_entries}, sort_keys=False, width=200),
        encoding="utf-8")

    reference = {
        "shared_standard_version": standard_version,
        "r1_repo": R1_REPO_NAME,
        "r1_commit": args.r1_commit,
        "r1_repository_version": repository_version(git(repo, "show", f"{args.r1_commit}:CHANGELOG.md")),
        "r1_core_schema_version": "0.1.0",
        "synchronized_at": synced_at,
        "schema_manifest": f"{CONTRACT_DIR}/manifest.yaml",
        "configuration_manifest": f"{CONTRACT_DIR}/manifest.yaml",
        "synthetic_manifest": "data/synthetic/manifest.yaml",
        "consumer_repo": R3_REPO_NAME,
        "rule": "R1 is authoritative. R3 changes the pin only through this tool, then rebuilds and revalidates.",
    }
    (ROOT / "standard/standard-reference.yaml").write_text(
        "# The R1 version this workbook implements. Updated only by tools/sync_r1_contracts.py.\n"
        + yaml.safe_dump(reference, sort_keys=False, width=200), encoding="utf-8")
    print(f"pinned {len(contract_entries)} contract files and {len(synthetic_entries)} synthetic files at {args.r1_commit}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
