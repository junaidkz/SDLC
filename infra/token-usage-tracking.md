# Token Usage Tracking — Honest Guide

## TL;DR

The agent-action audit pipeline (`audit_log.py` → JSONL → Elasticsearch → Kibana) captures **what the agents did**: tool calls, file touches, REQ-IDs, decisions, latency, errors. It does **not** capture token counts, and trying to make it do so was speculative — Copilot Chat in VS Code does not expose per-turn token counts to custom agents.

For token / cost tracking, use one of three official paths below — picked by where you run Copilot.

## Path 1 — VS Code Copilot Chat: enable OTel

This is the path Microsoft documents. Settings live in `infra/vscode-settings-otel.json`. Two sub-modes:

### File mode (per developer)

```jsonc
"github.copilot.chat.otel.enabled": true,
"github.copilot.chat.otel.exporterType": "file",
"github.copilot.chat.otel.outfile": "${env:HOME}/.copilot/otel/copilot-otel.jsonl"
```

Now every Copilot Chat turn appends an OTel JSONL record with input/output tokens, model, tool calls, and timing — following [OTel GenAI Semantic Conventions](https://opentelemetry.io/docs/specs/semconv/gen-ai/).

### OTLP mode (centralised)

Point at an OTel Collector that fans out to your preferred backend:

- **Langfuse** — native OTLP GenAI ingestion, purpose-built for LLM observability.
- **Azure Application Insights** — if you're already on Azure.
- **Grafana Tempo + Loki** — if you're on the Grafana stack.

Microsoft publishes a ready-made Grafana dashboard for this exact pipeline.

## Path 2 — Copilot CLI: read session telemetry directly

The Copilot CLI already writes per-session events to:

```
~/.copilot/session-state/<session-id>/events.jsonl
```

Token counts are in there as first-class fields. No configuration needed. Join to `audit_log.py` output by session id.

## Path 3 — Org-wide rollup: GitHub Enterprise usage API

For chargeback / capacity planning rather than per-step debugging:

```
GET /orgs/{org}/copilot/usage
```

Day-level per-user aggregates. Less granular than OTel, but it's the authoritative billing source. Requires Copilot Enterprise.

## What the agent audit pipeline IS authoritative for

Keep using `audit_log.py` → Elasticsearch → Kibana for:

- Which agent ran what tool, when, for which REQ-ID.
- File touches per session.
- Reviewer rejection loops per REQ-ID.
- Plan-step-to-implementation traceability.
- Latency per agent step.
- Error rates per tool.

These are the things only the orchestrator knows. Copilot's own telemetry doesn't tell you "this edit was for REQ-AUTH-014" — that link only exists in the audit pipeline.

## Joining the two pipelines in the dashboard

In Kibana (or whichever backend), join by:

- `session_id` if you set `COPILOT_SESSION` as an env var both pipelines pick up (recommended).
- Else by `(actor, timestamp ± 60s, model)`.

A cost-per-REQ-ID dashboard becomes: filter OTel events by session id → group by REQ-ID via the audit index → sum tokens × rate.

## What was wrong in earlier versions

`enrich_audit_with_tokens.py` (removed in this fix) assumed Copilot Chat wrote per-turn JSON logs to `~/.config/github-copilot/logs/` and similar paths. **It doesn't.** That path either doesn't exist or has a different schema. The script would run, find nothing, and silently produce zero enrichment. The correct path is enabling OTel as documented above.
