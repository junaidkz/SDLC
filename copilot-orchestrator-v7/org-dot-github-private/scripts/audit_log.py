#!/usr/bin/env python3
"""
audit_log.py — minimal audit emitter for the Copilot orchestrator agents.

Agents call this via a VS Code task at the start/end of each step. Writes
one JSONL line per call to .copilot/audit/<session-id>.jsonl. Stdlib only.

Usage from a task definition:
  python scripts/audit_log.py \
    --session "$COPILOT_SESSION" \
    --agent implementer \
    --model claude-sonnet-4.5 \
    --phase end \
    --tool editFiles \
    --tool-status ok \
    --files src/Auth/RefreshTokenService.cs \
    --req-ids REQ-AUTH-014 \
    --jira PLAT-1234 \
    --scenario-tags @AC-1 \
    --tokens-in 1842 \
    --tokens-out 603 \
    --latency-ms 8421
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path


def git_safe(args: list[str], default: str = "") -> str:
    try:
        return subprocess.run(
            ["git", *args], check=True, capture_output=True, text=True, timeout=3
        ).stdout.strip()
    except Exception:  # noqa: BLE001
        return default


def parse() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--session", default=os.environ.get("COPILOT_SESSION") or str(uuid.uuid4()))
    p.add_argument("--agent", required=True)
    p.add_argument("--model", required=True)
    p.add_argument("--phase", choices=["start", "end"], default="end")
    p.add_argument("--tool", default="")
    p.add_argument("--tool-status", default="ok")
    p.add_argument("--files", nargs="*", default=[])
    p.add_argument("--args", default="")            # arbitrary string, will be hashed not stored
    p.add_argument("--req-ids", nargs="*", default=[])
    p.add_argument("--jira", nargs="*", default=[])
    p.add_argument("--scenario-tags", nargs="*", default=[])
    p.add_argument("--tokens-in", type=int, default=0)
    p.add_argument("--tokens-out", type=int, default=0)
    p.add_argument("--latency-ms", type=int, default=0)
    p.add_argument("--cost-usd", type=float, default=0.0)
    p.add_argument("--error", default="")
    return p.parse_args()


def main() -> int:
    a = parse()
    audit_dir = Path(os.environ.get("COPILOT_AUDIT_DIR") or str(Path.home() / ".copilot" / "audit"))
    audit_dir.mkdir(parents=True, exist_ok=True)
    doc = {
        "@timestamp": datetime.now(timezone.utc).isoformat(),
        "session_id": a.session,
        "step_id": str(uuid.uuid4()),
        "agent": a.agent,
        "model": a.model,
        "phase": a.phase,
        "tool": a.tool,
        "tool_status": a.tool_status,
        "files": a.files,
        "args_hash": hashlib.sha256(a.args.encode()).hexdigest() if a.args else "",
        "req_ids": a.req_ids,
        "jira_keys": a.jira,
        "scenario_tags": a.scenario_tags,
        "commit_sha": git_safe(["rev-parse", "HEAD"]),
        "branch": git_safe(["rev-parse", "--abbrev-ref", "HEAD"]),
        "actor": os.environ.get("USER") or os.environ.get("USERNAME") or "unknown",
        "repo": git_safe(["remote", "get-url", "origin"]).split("/")[-1].removesuffix(".git"),
        "tokens_in": a.tokens_in,
        "tokens_out": a.tokens_out,
        "latency_ms": a.latency_ms,
        "cost_usd": a.cost_usd,
        "error": a.error,
        "user_message_redacted": True,
    }
    target = audit_dir / f"{a.session}.jsonl"
    with target.open("a", encoding="utf-8") as f:
        f.write(json.dumps(doc) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
