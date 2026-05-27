---
name: emit-audit
description: "Use whenever an agent step starts or ends. Emits a single JSONL audit event via the `audit:log` VS Code task to `~/.copilot/audit/<session>.jsonl`. Token counts (tokens_in/out, cost_usd) are emitted as 0 in real time in VS Code Copilot and should be analyzed from OTel telemetry separately. Every agent must invoke this skill at step boundaries."
user-invokable: false
disable-model-invocation: false
allowed-tools: ['runTasks']
---

# Emit an audit event

Every step boundary (start + end of a tool call, plus the final hand-off) emits one JSONL line via the `audit:log` task. The Reviewer fails the build when audit events are missing for tool calls that touched files.

## When to invoke

- **Before** every `editFiles`, `runTasks`, or external call.
- **After** every such call, with `tool_status: ok|error|rejected` and `latency-ms`.
- **At hand-off** from one agent to another (phase=`end`, tool=`handoff`).

## When NOT to invoke
- You're emitting from outside an agent step (per-step audit; orphaned events from helper code aren't useful).
- The action is a pure read with no file effect AND no decision impact.
- During a session where `COPILOT_SESSION` is unset — that's a setup bug.

## Required fields per call

| Field | Source | Notes |
|---|---|---|
| `session` | `$COPILOT_SESSION` (Orchestrator sets at session start) | required |
| `agent` | Your name from frontmatter | required |
| `model` | Your model from frontmatter | required |
| `phase` | `start` or `end` | required |
| `tool` | Tool name (or `handoff`) | required |
| `tool-status` | `ok` / `error` / `rejected` / `pending` | on `end` only |
| `files` | Files the tool touched (paths only) | on `end` when relevant |
| `req-ids` | REQ-IDs in scope | when known |
| `jira` | Jira key(s) in scope | when known |
| `latency-ms` | End − start in ms | on `end` |
| `tokens-in` / `tokens-out` | **Leave at 0** — see below | |

## Token counts — important

Inside a VS Code Copilot chat, **you cannot see your own token counts**. There is no API surface that exposes per-turn `prompt_tokens` / `completion_tokens` to a custom agent. Anyone claiming to is guessing.

Do not estimate, do not guess from character counts, do not make them up. **Leave `tokens-in` and `tokens-out` at their default of 0.** The fields exist in the schema so they can be back-filled.

For token and cost reporting in this root bundle, use OTel as documented in `infra/token-usage-tracking.md` and `infra/vscode-settings-otel.jsonc`.

## How to invoke

Call the `audit:log` task with arguments matching `scripts/audit_log.py`:

```
runTasks → audit:log
  args: --session "$COPILOT_SESSION" --agent <self> --model <self> \
        --phase end --tool <tool> --tool-status ok \
        --files <paths...> --req-ids REQ-XXX-NNN --jira PLAT-NNNN \
        --latency-ms N
```

Note no `--tokens-in/--tokens-out`. Skip those flags.

## What never goes in the audit

- Prompts, completions, file contents, user messages, secrets.
- The Elasticsearch mapping is `dynamic: strict` — unknown fields are rejected at ingest. If you find yourself wanting a free-text field, **stop**: that's a signal you're about to leak content.
- Use `--args "<string>"` only when you want a SHA-256 hash of the args recorded (not the args themselves).

## Enrichment cadence (recommended)

Use one of the documented telemetry paths in `infra/token-usage-tracking.md` for token analytics, and continue shipping audit events with `scripts/ship_audit_to_es.py`.

## Failure mode

If the `audit:log` task isn't defined in `.vscode/tasks.json`, surface that to the user. **Do not silently skip auditing.** A missing audit task means the orchestrator is mis-installed; the Reviewer treats missing audit events as a `blocking` finding.
