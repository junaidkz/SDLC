#!/usr/bin/env python3
"""
validate_plan.py — sanity-check a plan file produced by the Planner.

Called by the Planner just before the user-approval gate, and again by the
Implementer when it picks up the plan. Catches:
  - Files in 'Affected surface' that don't exist (when marked as 'modify' not 'new')
  - AC references in steps that don't appear in the feature file
  - Steps without AC tags
  - AC → test mapping table missing rows for any AC in the feature file
  - 'New: <path>' entries where the parent directory doesn't exist (likely typo)

Stdlib only.

Usage:
  python scripts/validators/validate_plan.py .copilot/plans/REQ-AUTH-014-2026-05-22.md
  python scripts/validators/validate_plan.py --plan <path> --json

Exit codes:
  0  plan is well-formed and references real files/ACs
  1  plan has issues (details on stderr)
  2  wiring error
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


REQ_ID_RE = re.compile(r"REQ-[A-Z]+-\d{3}")
AC_TAG_RE = re.compile(r"@(AC-\d+)\b")
PLAN_REQID_HEADING = re.compile(r"^##\s+Plan\s+—\s+(REQ-[A-Z]+-\d{3})", re.MULTILINE)
FEATURE_REF_RE = re.compile(r"^`(features/[^`]+\.feature)`", re.MULTILINE)

# Affected-surface entries: "- `path/to/file.cs` — description"
#                          or "- NEW `path/to/file.cs` — description"
SURFACE_LINE_RE = re.compile(
    r"^-\s+(NEW\s+)?`([^`]+)`\s*[—-]",
    re.MULTILINE,
)

# Step lines: "1. [AC-1] action — `path`"
STEP_LINE_RE = re.compile(
    r"^\d+\.\s+\[(AC-\d+)\]\s+.+?[—-]\s+`([^`]+)`",
    re.MULTILINE,
)

# AC mapping table rows: "| AC-1 | @REQ-XXX-NNN @AC-1 | tests/... | ... |"
MAPPING_AC_RE = re.compile(r"^\|\s*(AC-\d+)\s*\|", re.MULTILINE)


def die(rc: int, msg: str, *, as_json: bool = False) -> None:
    print(msg, file=sys.stderr)
    if as_json:
        print(json.dumps({"ok": False, "error": msg}))
    sys.exit(rc)


def find_section(text: str, heading: str) -> str:
    """Return content of '### <heading>' up to the next '###' or '##'."""
    pattern = re.compile(rf"^###\s+{re.escape(heading)}\s*\n(.*?)(?=^###?\s|\Z)",
                          re.MULTILINE | re.DOTALL)
    m = pattern.search(text)
    return m.group(1) if m else ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("plan", help="path to the plan markdown file")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    plan_path = Path(args.plan)
    if not plan_path.exists():
        die(2, f"plan not found: {plan_path}", as_json=args.json)
        return 2
    text = plan_path.read_text(encoding="utf-8")

    issues: list[str] = []

    # 1. Plan must have a REQ-ID heading
    req_m = PLAN_REQID_HEADING.search(text)
    if not req_m:
        issues.append("missing heading: '## Plan — REQ-XXX-NNN'")
        die(1, "\n".join(issues), as_json=args.json)
        return 1
    req_id = req_m.group(1)

    # 2. Plan must reference a real .feature file
    feature_section = find_section(text, "Feature reference")
    feat_m = FEATURE_REF_RE.search(feature_section)
    if not feat_m:
        issues.append("missing feature reference path")
    else:
        feature_path = Path(feat_m.group(1))
        if not feature_path.exists():
            issues.append(f"feature file not found: {feature_path}")
        else:
            feature_text = feature_path.read_text(encoding="utf-8")
            feature_acs = set(AC_TAG_RE.findall(feature_text))

            # 3. Surface entries — files marked as modify must exist; new files: parent dir must exist
            surface_section = find_section(text, "Affected surface")
            for m in SURFACE_LINE_RE.finditer(surface_section):
                is_new = bool(m.group(1))
                path_str = m.group(2)
                p = Path(path_str)
                if is_new:
                    if not p.parent.exists() and str(p.parent) != ".":
                        issues.append(f"NEW '{path_str}': parent dir {p.parent} doesn't exist (typo?)")
                else:
                    if not p.exists():
                        issues.append(f"'{path_str}' in Affected surface does not exist (mark as NEW if intentional)")

            # 4. Steps must tag a real AC + reference a path
            steps_section = find_section(text, "Steps")
            step_acs: set[str] = set()
            n_steps = 0
            for m in STEP_LINE_RE.finditer(steps_section):
                n_steps += 1
                ac, path_str = m.group(1), m.group(2)
                step_acs.add(ac)
                if f"@{ac}" not in feature_text:
                    issues.append(f"step references {ac} but feature file has no @{ac} tag")
            if n_steps == 0:
                issues.append("no well-formed steps found (expected '1. [AC-N] action — `path`')")

            # 5. AC → test mapping table must cover every AC in the feature file
            mapping_section = find_section(text, "AC → test mapping")
            mapping_acs = set(MAPPING_AC_RE.findall(mapping_section))
            missing_mappings = feature_acs - mapping_acs
            if missing_mappings:
                issues.append(f"AC mapping table missing rows for: {sorted(missing_mappings)}")

            # 6. Every AC in the feature must be touched by at least one step
            unstepped_acs = feature_acs - step_acs
            if unstepped_acs:
                issues.append(f"no step covers ACs: {sorted(unstepped_acs)}")

    # 7. Dependencies — if listed, every entry should propose an ADR ID
    deps_section = find_section(text, "Dependencies")
    if "**none**" not in deps_section and "none" not in deps_section.lower():
        if not re.search(r"ADR-\d{4}", deps_section):
            issues.append("Dependencies section lists packages but no proposed ADR-NNNN ID")

    if issues:
        print(f"INVALID plan {plan_path}:", file=sys.stderr)
        for i in issues:
            print(f"  - {i}", file=sys.stderr)
        if args.json:
            print(json.dumps({"ok": False, "req_id": req_id, "issues": issues}))
        return 1

    if args.json:
        print(json.dumps({"ok": True, "req_id": req_id, "n_steps": n_steps,
                          "acs_covered": sorted(step_acs)}))
    else:
        print(f"OK plan {plan_path} req_id={req_id} steps={n_steps} acs={sorted(step_acs)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
