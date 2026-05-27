#!/usr/bin/env python3
"""validate_skills.py — check every SKILL.md has valid YAML frontmatter
with the required Anthropic skill fields. Used by CI."""

import re
import sys
from pathlib import Path

import yaml  # type: ignore

REQUIRED = {"name", "description"}
KNOWN = REQUIRED | {"user-invokable", "disable-model-invocation", "allowed-tools", "license"}
MAX_LINES = 500
MIN_DESC_LEN = 30


def check_skill(path: Path) -> list[str]:
    errs: list[str] = []
    text = path.read_text(encoding="utf-8")

    # Length cap (Anthropic guideline)
    if text.count("\n") > MAX_LINES:
        errs.append(f"{path}: {text.count(chr(10))} lines > {MAX_LINES} max — move detail to references/")

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
        print(f"{path}: warning — non-standard fields: {sorted(extras)}", file=sys.stderr)

    desc = (data.get("description") or "").strip()
    if len(desc) < MIN_DESC_LEN:
        errs.append(f"{path}: description too short ({len(desc)} chars; need >= {MIN_DESC_LEN} for triggering)")
    if not any(verb in desc.lower() for verb in ("use ", "invoke", "call ", "apply", "when ")):
        errs.append(f"{path}: description should start with a use-trigger verb (e.g. 'Use when...')")

    # Require both "When to use" and "When NOT to use" sections (Anthropic best practice)
    if "## When to use" not in text and "## When to invoke" not in text:
        errs.append(f"{path}: missing '## When to use' (or '## When to invoke') section")
    if "## When NOT to use" not in text and "## When NOT to invoke" not in text:
        errs.append(f"{path}: missing '## When NOT to use' (or '## When NOT to invoke') section")

    return errs


def main(roots: list[str]) -> int:
    all_errs: list[str] = []
    for root in roots:
        for p in Path(root).rglob("SKILL.md"):
            all_errs.extend(check_skill(p))
    for e in all_errs:
        print(f"::error::{e}", file=sys.stderr)
    if all_errs:
        return 1
    print(f"validated skills under {roots}: all clean")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:] or ["skills"]))
