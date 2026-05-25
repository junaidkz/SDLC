---
name: emit-audit
description: Use whenever an agent step starts or ends. Emits a single JSONL audit event via the `audit:log` VS Code task to `~/.copilot/audit/<session>.jsonl`. Every agent (Initiator, Orchestrator, Requirements Gatherer, Planner, Implementer, Reviewer) must invoke this skill at step boundaries so the Elasticsearch/Kibana audit trail stays complete.
user-invokable: false
disable-model-invocation: false
allowed-tools: ['runTasks']
---

# Emit an audit event

Every step boundary (start + end of a tool call, plus the final hand-off) emits one JSONL line via the `audit:log` task. This is non-negotiable — the Reviewer fails the build when audit events are missing for tool calls that touched files.

## When to invoke

- **Before** every `editFiles`, `runTasks`, or external call.
- **After** every such call, with `tool_status: ok|error|rejected` and timing.
- **At hand-off** from one agent to another (phase=`end`, tool=`handoff`).

## Required fields per call

| Field | Source |
|---|---|
| `session` | Env var `COPILOT_SESSION` (the Orchestrator generates and exports this on session start) |
| `agent` | Your agent name from frontmatter |
| `model` | Your model from frontmatter |
| `phase` | `start` or `end` |
| `tool` | The tool name you're about to call (or `handoff`) |
| `tool-status` | `ok` / `error` / `rejected` / `pending` |
| `files` | Files the tool touched (paths only, never contents) |
| `req-ids` | REQ-IDs in scope |
| `jira` | Jira key(s) in scope |
| `tokens-in/out` | If known; omit when unknown |
| `latency-ms` | End − start in milliseconds, on `phase=end` |

## How to invoke

Use `runTasks` to call the `audit:log` task with arguments matching `scripts/audit_log.py`:

```
runTasks → audit:log
  args: --session "$COPILOT_SESSION" --agent <self> --model <self> \
        --phase end --tool <tool> --tool-status ok \
        --files <paths...> --req-ids REQ-XXX-NNN --jira PLAT-NNNN \
        --tokens-in N --tokens-out N --latency-ms N
```

## What never goes in the audit

- Prompts, completions, file contents, user messages, secrets.
- The Elasticsearch mapping is `dynamic: strict` — unknown fields are rejected at ingest. If you find yourself wanting a free-text field, **stop**: that's a signal you're about to leak content.
- Use `--args "<string>"` only when you want a SHA-256 hash of the args recorded (not the args themselves).

## Failure mode

If the task isn't defined in `.vscode/tasks.json`, surface that to the user — do not silently skip auditing. A missing audit task means the orchestrator is mis-installed.
