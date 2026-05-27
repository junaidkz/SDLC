#!/usr/bin/env python3
"""validate_agents.py — check every *.agent.md has valid YAML frontmatter
with the required fields. Used by CI to fail PRs that break the agent format."""

import re
import sys
from pathlib import Path

import yaml  # type: ignore

REQUIRED = {"name", "description"}
KNOWN = REQUIRED | {"model", "tools", "target", "handoffs", "argument-hint", "color"}


def check_agent(path: Path) -> list[str]:
    errs: list[str] = []
    text = path.read_text(encoding="utf-8")
    m = re.match(r"---\n(.*?)\n---\n", text, re.DOTALL)
    if not m:
        return [f"{path}: missing YAML frontmatter"]
    try:
        data = yaml.safe_load(m.group(1))
    except yaml.YAMLError as e:
        return [f"{path}: YAML parse error — {e}"]
    if not isinstance(data, dict):
        return [f"{path}: frontmatter is not a mapping"]
    missing = REQUIRED - set(data.keys())
    if missing:
        errs.append(f"{path}: missing required fields: {sorted(missing)}")
    extras = set(data.keys()) - KNOWN
    if extras:
        print(f"{path}: warning — non-standard frontmatter fields: {sorted(extras)}", file=sys.stderr)
    desc = (data.get("description") or "").strip()
    if len(desc) < 20:
        errs.append(f"{path}: description too short ({len(desc)} chars; need >= 20)")

    # Handoff sanity — every handoff prompt should be multi-line (use YAML | literal)
    # and either reference a variable or be one of the documented escape paths.
    for h in data.get("handoffs", []) or []:
        label, prompt = h.get("label", ""), h.get("prompt", "")
        if "\n" not in prompt and not any(k in label.lower() for k in ("abort", "rediscover", "re-discover", "pause")):
            errs.append(f"{path}: handoff {label!r} prompt is single-line — likely lossy; use YAML | block")
    return errs


def main(roots: list[str]) -> int:
    all_errs: list[str] = []
    for root in roots:
        for p in Path(root).rglob("*.agent.md"):
            all_errs.extend(check_agent(p))
    for e in all_errs:
        print(f"::error::{e}", file=sys.stderr)
    if all_errs:
        return 1
    print(f"validated agents under {roots}: all clean")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:] or [".github/agents"]))
