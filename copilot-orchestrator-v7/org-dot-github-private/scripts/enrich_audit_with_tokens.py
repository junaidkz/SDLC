#!/usr/bin/env python3
"""
enrich_audit_with_tokens.py — back-fills tokens_in / tokens_out / cost_usd on
audit events that didn't have them at emit time.

Why this exists: inside a VS Code Copilot chat, the agent doesn't see its own
token counts. So `audit_log.py` writes events with tokens_in=0 / tokens_out=0
unless explicitly told. This script enriches those events from one of two
authoritative sources:

  1. GitHub Copilot Enterprise audit/billing API (if --source=github + token).
     Fetches usage records and joins on (actor, model, timestamp window).

  2. Local Copilot session logs on the developer machine. Each Copilot Chat
     turn writes a record under:
       ~/.config/github-copilot/logs/  (Linux)
       ~/Library/Logs/github-copilot/  (macOS)
       %APPDATA%/github-copilot/logs/  (Windows)
     We parse those for token usage and join on timestamp.

The script can also re-index the enriched events back to Elasticsearch
(--reindex), or just rewrite the local JSONL files in place (--rewrite).

Stdlib only. Idempotent: events with non-zero tokens_in are skipped.

Usage:
  python scripts/enrich_audit_with_tokens.py --source local --rewrite
  python scripts/enrich_audit_with_tokens.py --source github --reindex \\
      --since 2026-05-22T00:00:00Z --until 2026-05-23T00:00:00Z

Env (for --source github):
  GITHUB_TOKEN         PAT with copilot:read scope
  GITHUB_ORG           org slug
"""

from __future__ import annotations

import argparse
import base64
import glob
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path


# ── Cost table (USD per 1M tokens) ─────────────────────────────────────────
# Hard-coded fallback for cost calculation when the source doesn't supply it.
# Tune to your contract. These are illustrative.

COST_PER_M = {
    # input,  output
    "claude-sonnet-4.5":   (3.00, 15.00),
    "claude-opus-4.7":     (15.00, 75.00),
    "claude-haiku-4.5":    (1.00,  5.00),
    "gpt-5":               (5.00, 15.00),
    "gpt-5-mini":          (0.25,  2.00),
    "o3":                  (15.00, 60.00),
}


def cost_usd(model: str, tin: int, tout: int) -> float:
    rates = COST_PER_M.get(model.lower())
    if not rates:
        return 0.0
    cin, cout = rates
    return round((tin / 1_000_000) * cin + (tout / 1_000_000) * cout, 6)


# ── Local Copilot log discovery ────────────────────────────────────────────

def copilot_log_dirs() -> list[Path]:
    home = Path.home()
    candidates = [
        home / ".config" / "github-copilot" / "logs",
        home / "Library" / "Logs" / "github-copilot",
        Path(os.environ.get("APPDATA", "")) / "github-copilot" / "logs" if os.environ.get("APPDATA") else None,
    ]
    return [p for p in candidates if p and p.exists()]


def read_local_copilot_usage(since: datetime, until: datetime) -> list[dict]:
    """Returns records: {ts, model, tokens_in, tokens_out, actor}."""
    out: list[dict] = []
    for d in copilot_log_dirs():
        for f in d.glob("*.log"):
            try:
                with f.open("r", encoding="utf-8", errors="replace") as fh:
                    for line in fh:
                        line = line.strip()
                        if not line.startswith("{"):
                            continue
                        try:
                            r = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        usage = r.get("usage") or r.get("token_usage")
                        if not isinstance(usage, dict):
                            continue
                        ts = r.get("timestamp") or r.get("@timestamp") or r.get("ts")
                        if not ts:
                            continue
                        try:
                            t = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                        except ValueError:
                            continue
                        if t < since or t > until:
                            continue
                        out.append({
                            "ts": t,
                            "model": r.get("model") or "",
                            "tokens_in": int(usage.get("prompt_tokens", usage.get("input_tokens", 0))),
                            "tokens_out": int(usage.get("completion_tokens", usage.get("output_tokens", 0))),
                            "actor": r.get("actor") or os.environ.get("USER") or "",
                        })
            except OSError:
                continue
    return out


# ── GitHub Copilot Enterprise usage API ────────────────────────────────────

def read_github_copilot_usage(since: datetime, until: datetime) -> list[dict]:
    token = os.environ.get("GITHUB_TOKEN")
    org = os.environ.get("GITHUB_ORG")
    if not token or not org:
        print("set GITHUB_TOKEN and GITHUB_ORG to use --source github", file=sys.stderr)
        return []
    url = f"https://api.github.com/orgs/{org}/copilot/usage"
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read())
    except urllib.error.HTTPError as e:
        print(f"GitHub API error: {e.code} {e.reason}", file=sys.stderr)
        return []
    out: list[dict] = []
    # The org-level usage endpoint returns aggregates by day, not per-turn.
    # For per-step joining you need the audit-log API; included here as best-effort
    # daily attribution. Per-developer enrichment requires GitHub Copilot Metrics API
    # (Enterprise only) — adapt this function to your tenant.
    for day in data if isinstance(data, list) else []:
        ts = datetime.fromisoformat(day["day"] + "T12:00:00+00:00")
        if ts < since or ts > until:
            continue
        out.append({
            "ts": ts,
            "model": "",
            "tokens_in": int(day.get("total_prompt_tokens") or 0),
            "tokens_out": int(day.get("total_completion_tokens") or 0),
            "actor": "",
        })
    return out


# ── Join logic ─────────────────────────────────────────────────────────────

def find_usage_match(event: dict, usage: list[dict], window_s: int = 60) -> dict | None:
    """Find the closest usage record by (model, actor, timestamp ±window_s)."""
    ts = datetime.fromisoformat(event["@timestamp"].replace("Z", "+00:00"))
    model = (event.get("model") or "").lower()
    actor = event.get("actor") or ""
    best, best_dt = None, timedelta(seconds=window_s + 1)
    for u in usage:
        if u["model"] and u["model"].lower() != model:
            continue
        if u["actor"] and actor and u["actor"] != actor:
            continue
        dt = abs(u["ts"] - ts)
        if dt < best_dt:
            best_dt, best = dt, u
    return best if best and best_dt <= timedelta(seconds=window_s) else None


# ── Enrichment loop ────────────────────────────────────────────────────────

def enrich_event(event: dict, usage: list[dict]) -> bool:
    """Returns True if the event was enriched."""
    if int(event.get("tokens_in") or 0) > 0 or int(event.get("tokens_out") or 0) > 0:
        return False  # already has counts
    match = find_usage_match(event, usage)
    if not match:
        return False
    event["tokens_in"] = match["tokens_in"]
    event["tokens_out"] = match["tokens_out"]
    event["cost_usd"] = cost_usd(event.get("model", ""), match["tokens_in"], match["tokens_out"])
    event["_enriched_at"] = datetime.now(timezone.utc).isoformat()
    return True


def rewrite_jsonl_files(audit_dir: Path, usage: list[dict]) -> tuple[int, int]:
    """Rewrites *.jsonl files in place. Returns (events_seen, events_enriched)."""
    seen = enriched = 0
    for f in audit_dir.glob("*.jsonl"):
        lines = []
        changed = False
        with f.open("r", encoding="utf-8") as fh:
            for raw in fh:
                raw = raw.strip()
                if not raw:
                    continue
                seen += 1
                try:
                    ev = json.loads(raw)
                except json.JSONDecodeError:
                    lines.append(raw)
                    continue
                if enrich_event(ev, usage):
                    enriched += 1
                    changed = True
                lines.append(json.dumps(ev))
        if changed:
            tmp = f.with_suffix(".jsonl.tmp")
            tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")
            tmp.replace(f)
    return seen, enriched


# ── Main ───────────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source", choices=["local", "github"], default="local")
    ap.add_argument("--audit-dir", default=os.environ.get("COPILOT_AUDIT_DIR") or str(Path.home() / ".copilot" / "audit"))
    ap.add_argument("--since", help="ISO-8601; default: 7 days ago")
    ap.add_argument("--until", help="ISO-8601; default: now")
    ap.add_argument("--rewrite", action="store_true", help="rewrite local JSONL in place")
    ap.add_argument("--reindex", action="store_true", help="POST enriched events to ES via _bulk update")
    args = ap.parse_args()

    now = datetime.now(timezone.utc)
    since = datetime.fromisoformat(args.since.replace("Z", "+00:00")) if args.since else now - timedelta(days=7)
    until = datetime.fromisoformat(args.until.replace("Z", "+00:00")) if args.until else now

    if args.source == "local":
        usage = read_local_copilot_usage(since, until)
    else:
        usage = read_github_copilot_usage(since, until)

    print(f"loaded {len(usage)} usage record(s) from {args.source}")
    if not usage:
        print("nothing to enrich with; exiting")
        return 0

    audit_dir = Path(args.audit_dir)
    if not audit_dir.exists():
        print(f"no audit dir: {audit_dir}", file=sys.stderr)
        return 1

    if args.rewrite:
        seen, enriched = rewrite_jsonl_files(audit_dir, usage)
        print(f"rewrote: {enriched}/{seen} events enriched")

    if args.reindex:
        print("--reindex not implemented in this stub; ship_audit_to_es.py picks up rewritten files")

    return 0


if __name__ == "__main__":
    sys.exit(main())
