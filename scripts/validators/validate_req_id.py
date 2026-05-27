#!/usr/bin/env python3
"""
validate_req_id.py — verify a REQ-ID actually exists.

Called by Orchestrator, Planner, and Implementer before acting on a REQ-ID.
Catches the most common hallucination: an agent (or user typo) referencing
REQ-AUTH-014 when only REQ-AUTH-013 exists.

Checks:
  1. The ID appears as a heading in docs/requirements.md.
  2. Its status is 'approved' or 'in-progress' (not 'draft' or 'deprecated').
  3. Exactly one .feature file under features/ has matching `req_id:` frontmatter.
  4. Every @AC-N tag in that .feature file is accounted for in requirements.md.

Stdlib only.

Usage:
  python scripts/validators/validate_req_id.py REQ-AUTH-014
  python scripts/validators/validate_req_id.py REQ-AUTH-014 --json    # machine-readable

Exit codes:
  0  REQ-ID exists, approved/in-progress, has a feature file, ACs consistent
  1  REQ-ID problem (details on stderr)
  2  wiring error (requirements.md missing, etc.)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REQ_ID_RE = re.compile(r"^##\s+(REQ-[A-Z]+-\d{3})\s*$", re.MULTILINE)
STATUS_RE = re.compile(r"\*\*Status:\*\*\s*(\w[\w-]*)", re.IGNORECASE)
AC_TAG_RE = re.compile(r"@(AC-\d+)\b")


def die(rc: int, msg: str, *, as_json: bool = False, payload: dict | None = None) -> None:
    if as_json:
        print(json.dumps({"ok": False, "error": msg, **(payload or {})}))
    else:
        print(msg, file=sys.stderr)
    sys.exit(rc)


def parse_requirements(req_md: Path) -> dict[str, dict]:
    """Return {req_id: {'status': ..., 'block': <markdown text>, 'acs': [...]}}."""
    if not req_md.exists():
        die(2, f"requirements file not found: {req_md}")
    text = req_md.read_text(encoding="utf-8")
    matches = list(REQ_ID_RE.finditer(text))
    out: dict[str, dict] = {}
    for i, m in enumerate(matches):
        req_id = m.group(1)
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        block = text[start:end]
        status_m = STATUS_RE.search(block)
        status = (status_m.group(1) if status_m else "unknown").lower()
        acs = sorted(set(re.findall(r"AC-\d+", block)))
        out[req_id] = {"status": status, "block": block, "acs": acs}
    return out


def find_feature_file(req_id: str, features_dir: Path) -> Path | None:
    if not features_dir.exists():
        return None
    for f in features_dir.rglob("*.feature"):
        text = f.read_text(encoding="utf-8")
        # frontmatter is in leading HTML-style comment lines
        if re.search(rf"^#\s*req_id:\s*{re.escape(req_id)}\s*$", text, re.MULTILINE):
            return f
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("req_id")
    ap.add_argument("--requirements", default="docs/requirements.md")
    ap.add_argument("--features-dir", default="features")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args()

    as_json = args.json

    if not re.fullmatch(r"REQ-[A-Z]+-\d{3}", args.req_id):
        die(1, f"malformed REQ-ID: {args.req_id} (expected REQ-AREA-NNN)", as_json=as_json)
        return 1

    reqs = parse_requirements(Path(args.requirements))
    if args.req_id not in reqs:
        die(1, f"{args.req_id} not in {args.requirements}. "
              f"Available: {', '.join(sorted(reqs)) or '(none)'}",
            as_json=as_json, payload={"available": sorted(reqs)})
        return 1

    entry = reqs[args.req_id]
    status = entry["status"]
    if status not in ("approved", "in-progress"):
        die(1, f"{args.req_id} status is '{status}'; must be 'approved' or 'in-progress'",
            as_json=as_json, payload={"status": status})
        return 1

    feature = find_feature_file(args.req_id, Path(args.features_dir))
    if feature is None:
        die(1, f"{args.req_id} has no matching .feature file under {args.features_dir}/",
            as_json=as_json)
        return 1

    # Cross-check ACs: every @AC-N in the .feature must appear in requirements.md
    feature_text = feature.read_text(encoding="utf-8")
    feature_acs = sorted(set(AC_TAG_RE.findall(feature_text)))
    req_acs = entry["acs"]
    missing_in_req = [ac for ac in feature_acs if ac not in req_acs]
    if missing_in_req:
        die(1, f"{args.req_id}: .feature file has ACs {missing_in_req} "
              f"that are not in requirements.md (req-md has {req_acs})",
            as_json=as_json,
            payload={"feature": str(feature), "feature_acs": feature_acs, "req_acs": req_acs})
        return 1

    result = {
        "ok": True,
        "req_id": args.req_id,
        "status": status,
        "feature_file": str(feature),
        "acs": feature_acs,
    }
    if as_json:
        print(json.dumps(result))
    else:
        print(f"OK {args.req_id} status={status} feature={feature} acs={','.join(feature_acs)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
