#!/usr/bin/env python3
"""
create_jira_from_feature.py

For each .feature file passed on the CLI (or auto-discovered under features/),
parse the leading frontmatter.
If `jira: pending`, create a Jira issue via REST and rewrite the file
(and docs/requirements.md) with the new key. Append the key to
.jira-keys-created for downstream tooling.

No third-party dependencies — stdlib only.
Env vars required:
  JIRA_BASE_URL, JIRA_PROJECT_KEY, JIRA_USER_EMAIL, JIRA_API_TOKEN
"""

from __future__ import annotations

import base64
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

FRONTMATTER_RE = re.compile(
    r"^(?P<header>(?:#\s*---\s*\n)(?P<body>(?:#.*\n)+?)(?:#\s*---\s*\n))",
    re.MULTILINE,
)
JIRA_PENDING_RE = re.compile(r"^#\s*jira:\s*pending\s*$", re.MULTILINE)
KEY_VAL_RE = re.compile(r"^#\s*(?P<k>[a-z_]+):\s*(?P<v>.+?)\s*$", re.MULTILINE)


def env(name: str) -> str:
    v = os.environ.get(name)
    if not v:
        sys.exit(f"missing env: {name}")
    return v


def auth_header() -> str:
    raw = f"{env('JIRA_USER_EMAIL')}:{env('JIRA_API_TOKEN')}".encode()
    return "Basic " + base64.b64encode(raw).decode()


def parse_frontmatter(text: str) -> tuple[dict, re.Match | None]:
    m = FRONTMATTER_RE.search(text)
    if not m:
        return {}, None
    fields = {km.group("k"): km.group("v") for km in KEY_VAL_RE.finditer(m.group("body"))}
    return fields, m


def extract_scenarios(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip().startswith("Scenario:")]


def extract_intent(text: str) -> str:
    # Pull the "As a / I want / So that" block if present
    block = []
    capture = False
    for line in text.splitlines():
        if line.strip().startswith("Feature:"):
            capture = True
            continue
        if capture:
            if line.strip().startswith(("As ", "I want", "So that")):
                block.append(line.strip())
            elif line.strip().startswith(("Background:", "Scenario:", "@")):
                break
    return "\n".join(block) or "(no intent block)"


def create_jira_issue(req_id: str, area: str, feature_path: Path, text: str) -> str:
    summary = f"[{req_id}] {feature_path.stem.replace('-', ' ').title()}"
    description = (
        f"*Source of truth:* `{feature_path}`\n\n"
        f"*Requirement ID:* {req_id}\n"
        f"*Area:* {area}\n\n"
        f"h3. Intent\n{{noformat}}\n{extract_intent(text)}\n{{noformat}}\n\n"
        f"h3. Scenarios\n" + "\n".join(f"* {s}" for s in extract_scenarios(text))
    )
    payload = {
        "fields": {
            "project": {"key": env("JIRA_PROJECT_KEY")},
            "summary": summary,
            "description": description,
            "issuetype": {"name": "Story"},
            "labels": ["bdd", "copilot-managed", area.lower().replace(" ", "-")],
        }
    }
    req = urllib.request.Request(
        url=f"{env('JIRA_BASE_URL').rstrip('/')}/rest/api/2/issue",
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": auth_header(),
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read())
    return data["key"]


def rewrite_jira_pending(path: Path, key: str) -> None:
    text = path.read_text(encoding="utf-8")
    new_text = JIRA_PENDING_RE.sub(f"# jira: {key}", text, count=1)
    path.write_text(new_text, encoding="utf-8")


def update_requirements_index(req_id: str, key: str) -> None:
    idx = Path("docs/requirements.md")
    if not idx.exists():
        return
    text = idx.read_text(encoding="utf-8")
    pattern = re.compile(
        rf"(## {re.escape(req_id)}.*?\*\*Jira:\*\* )pending",
        re.DOTALL,
    )
    new_text, n = pattern.subn(rf"\g<1>{key}", text)
    if n:
        idx.write_text(new_text, encoding="utf-8")


def main(argv: list[str]) -> int:
    created: list[str] = []
    if argv:
        args = argv
    else:
        args = [str(p) for p in sorted(Path("features").rglob("*.feature"))]
    for arg in args:
        path = Path(arg)
        if not path.exists():
            print(f"skip (missing): {path}")
            continue
        text = path.read_text(encoding="utf-8")
        fields, _ = parse_frontmatter(text)
        if not fields:
            print(f"skip (no frontmatter): {path}")
            continue
        if fields.get("jira", "").strip().lower() != "pending":
            print(f"skip (already linked): {path} -> {fields.get('jira')}")
            continue
        req_id = fields.get("req_id")
        if not req_id:
            print(f"skip (no req_id): {path}")
            continue
        area = fields.get("area", "General")
        try:
            key = create_jira_issue(req_id, area, path, text)
        except Exception as e:  # noqa: BLE001
            print(f"FAIL create for {path}: {e}", file=sys.stderr)
            return 1
        rewrite_jira_pending(path, key)
        update_requirements_index(req_id, key)
        created.append(key)
        print(f"created {key} for {req_id} ({path})")
    Path(".jira-keys-created").write_text("\n".join(created) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
