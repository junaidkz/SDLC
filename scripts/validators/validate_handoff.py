#!/usr/bin/env python3
"""
validate_handoff.py — validate a structured handoff payload against
.github/schemas/handoffs.schema.json before an agent fires the handoff.

Stdlib only. The agents invoke this via the `validate:handoff` VS Code task
just before clicking a handoff button. If the payload is malformed, the
agent must fix it and try again — never hand off bad data.

Usage:
  python scripts/validators/validate_handoff.py --kind RequirementsHandoff --payload payload.json
  python scripts/validators/validate_handoff.py --kind PlanHandoff --payload -    # reads from stdin

Exit codes:
  0  valid
  1  payload invalid (errors printed to stderr)
  2  config / wiring error (e.g. schema file missing)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCHEMA_PATH = Path(".github/schemas/handoffs.schema.json")
VALID_KINDS = ("RequirementsHandoff", "PlanHandoff", "ReviewVerdict", "AuditEvent")


def die(rc: int, msg: str) -> None:
    print(msg, file=sys.stderr)
    sys.exit(rc)


def load_schema(kind: str) -> dict:
    if not SCHEMA_PATH.exists():
        die(2, f"schema missing: {SCHEMA_PATH}")
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    defs = schema.get("$defs", {})
    if kind not in defs:
        die(2, f"unknown kind: {kind}. Valid: {VALID_KINDS}")
    return defs[kind]


def validate(payload: dict, sub_schema: dict, path: str = "$") -> list[str]:
    """Minimal JSON-Schema subset validator. Stdlib-only.

    Covers what we use: type, required, properties, items, enum, const, pattern,
    minItems, additionalProperties, allOf+if/then.
    """
    import re as _re

    errs: list[str] = []
    t = sub_schema.get("type")
    enum = sub_schema.get("enum")
    const = sub_schema.get("const")
    required = sub_schema.get("required", [])
    properties = sub_schema.get("properties", {})
    items = sub_schema.get("items")
    pattern = sub_schema.get("pattern")
    min_items = sub_schema.get("minItems")
    add_props = sub_schema.get("additionalProperties", True)

    if const is not None and payload != const:
        errs.append(f"{path}: expected const {const!r}, got {payload!r}")
        return errs
    if enum is not None and payload not in enum:
        errs.append(f"{path}: value {payload!r} not in enum {enum}")
        return errs

    if t == "object":
        if not isinstance(payload, dict):
            errs.append(f"{path}: expected object, got {type(payload).__name__}")
            return errs
        for req in required:
            if req not in payload:
                errs.append(f"{path}.{req}: required field missing")
        for k, v in payload.items():
            if k in properties:
                errs.extend(validate(v, properties[k], f"{path}.{k}"))
            elif add_props is False:
                errs.append(f"{path}.{k}: unexpected field (additionalProperties: false)")
        for clause in sub_schema.get("allOf", []):
            if_part = clause.get("if", {})
            then_part = clause.get("then", {})
            if_ok = not validate(payload, if_part, path)
            if if_ok:
                errs.extend(validate(payload, then_part, path))
    elif t == "array":
        if not isinstance(payload, list):
            errs.append(f"{path}: expected array")
            return errs
        if min_items is not None and len(payload) < min_items:
            errs.append(f"{path}: needs at least {min_items} items, got {len(payload)}")
        if items:
            for i, item in enumerate(payload):
                errs.extend(validate(item, items, f"{path}[{i}]"))
    elif t == "string":
        if not isinstance(payload, str):
            errs.append(f"{path}: expected string, got {type(payload).__name__}")
        elif pattern and not _re.match(pattern, payload):
            errs.append(f"{path}: {payload!r} does not match pattern {pattern}")
    elif t == "integer":
        if not isinstance(payload, int) or isinstance(payload, bool):
            errs.append(f"{path}: expected integer")
        elif "minimum" in sub_schema and payload < sub_schema["minimum"]:
            errs.append(f"{path}: {payload} < minimum {sub_schema['minimum']}")
    elif t == "number":
        if not isinstance(payload, (int, float)) or isinstance(payload, bool):
            errs.append(f"{path}: expected number")
    elif t == "boolean":
        if not isinstance(payload, bool):
            errs.append(f"{path}: expected boolean")
    return errs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--kind", required=True, choices=VALID_KINDS)
    ap.add_argument("--payload", required=True, help="path to JSON file, or '-' for stdin")
    args = ap.parse_args()

    if args.payload == "-":
        try:
            payload = json.load(sys.stdin)
        except json.JSONDecodeError as e:
            die(1, f"payload not valid JSON on stdin: {e}")
            return 1
    else:
        p = Path(args.payload)
        if not p.exists():
            die(2, f"payload file not found: {p}")
        try:
            payload = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            die(1, f"payload not valid JSON: {e}")
            return 1

    schema = load_schema(args.kind)
    errors = validate(payload, schema)
    if errors:
        print(f"INVALID {args.kind}:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1
    print(f"OK {args.kind}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
