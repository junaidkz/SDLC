# Traceability Architecture (v3 — no MCP, ES + Kibana stack)

Three layers. All three are needed for end-to-end traceability.

```
┌─────────────────────────────────────────────────────────────────┐
│ Layer 3: Agent-action audit                                     │
│   agents → JSONL → Filebeat (or bulk POST) → Elasticsearch      │
│                                                       → Kibana  │
└─────────────────────────────────────────────────────────────────┘
                                  │
┌─────────────────────────────────────────────────────────────────┐
│ Layer 2: Code → requirement                                     │
│   commit prefix + @req/@jira tags + test traits + RTM + CI gate │
└─────────────────────────────────────────────────────────────────┘
                                  │
┌─────────────────────────────────────────────────────────────────┐
│ Layer 1: Intent → requirement                                   │
│   Gherkin .feature + Jira (created by Requirements Gatherer)     │
└─────────────────────────────────────────────────────────────────┘
```

---

## Layer 1 — Intent → requirement

- **Author**: the Requirements Gatherer agent writes `features/<area>/*.feature` with `jira: pending` in the frontmatter and a row in `docs/requirements.md`.
- **Jira creation**: the Requirements Gatherer runs task `jira:create-from-pending`, which executes `scripts/create_jira_from_feature.py`, calls Jira REST (`POST /rest/api/2/issue`), and rewrites the key into both the feature file and requirements index.
- **PR linkage**: Implementer and Reviewer enforce `Refs: <key>` in commit bodies and PR body.

No MCP. Jira creation remains deterministic by using a checked-in script invoked by the agent task harness.

**Idempotency**: creation only acts when frontmatter is `jira: pending`. Re-running the task does not duplicate existing linked items.

---

## Layer 2 — Code → requirement

Unchanged from v2:

- Commits: `[REQ-AUTH-014] short summary` body `Refs: PLAT-1234`.
- Code: docstring `@req REQ-AUTH-014 @jira PLAT-1234`.
- Tests: `[Trait("req","REQ-AUTH-014")]` (xUnit) or `describe('@REQ-AUTH-014 @AC-1 ...')` (Jest).
- Ledger: `docs/traceability.md` — append-only on Reviewer approval.
- CI: `scripts/check-traceability.ps1` parses requirements.md + traceability.md + the PR's commit messages, fails the build when any AC is uncovered.

---

## Layer 3 — Agent-action audit (Elasticsearch + Kibana)

### Pipeline

```
agents
  │  (each step: start + end, via VS Code task)
  ▼
scripts/audit_log.py                  # stdlib only, append JSONL
  │
  ▼
~/.copilot/audit/<session>.jsonl
  │
  ├──► Filebeat (infra/filebeat.yml)          ──► Elasticsearch (write alias copilot-audit)
  │
  └──► OR scripts/ship_audit_to_es.py         ──► Elasticsearch (fallback, no Filebeat install)
                                                  │
                                                  ▼
                                           Kibana data view copilot-audit-*
                                                  │
                                                  ▼
                                           Dashboard tiles (see infra/kibana-setup.md)
```

### What each component does

| Component | File | Role |
|---|---|---|
| Emitter | `scripts/audit_log.py` | Stdlib Python. Called by agents via a VS Code task at start + end of each step. Writes one JSONL line per call. |
| Mapping | `infra/elastic-index-template.json` | Strict `dynamic: strict` mapping for the `copilot-audit-*` indices. Defines every field; unknown fields are rejected (defence against accidental prompt leakage). |
| Shipper (primary) | `infra/filebeat.yml` | Filebeat tails JSONL files, parses NDJSON, sends to ES. Survives offline laptops via on-disk registry. |
| Shipper (fallback) | `scripts/ship_audit_to_es.py` | Stdlib bulk POST to ES `_bulk`. Renames `.jsonl` → `.jsonl.sent` after success. Use when Filebeat isn't permitted on the dev machine. |
| Dashboard | `infra/kibana-setup.md` | Ten recommended tiles + saved searches + two alerts (unstamped edits, cost spike). |

### What gets logged

Per agent step (start and end): timestamp, session id, agent, model, phase, tool, tool status, files touched, args hash, REQ-IDs, Jira keys, scenario tags, commit/branch/repo/actor, tokens in/out, latency, cost, error.

**Not logged**: prompts, completions, file contents, user messages. Mapping is `dynamic: strict` and Filebeat drops `message`/`prompt`/`completion` fields if they ever appear — defence in depth.

### Sample queries the dashboard answers

- *"Show me every action taken on REQ-AUTH-014, in order, across all sessions."* — query `req_ids:"REQ-AUTH-014"`, sort by `@timestamp`.
- *"How many times did the Reviewer reject this week, and on which REQ-IDs?"* — query `agent:"reviewer" AND tool_status:"rejected" AND @timestamp >= now-7d`, group by `req_ids`.
- *"What's our token spend per REQ-ID this month?"* — table viz, sum of `cost_usd`, group by `req_ids`.
- *"Which files were touched by tool calls without REQ-ID tagging?"* — saved alert search, should always be empty.
- *"Full replay of session X for incident investigation"* — query `session_id:"X"`, sort asc.

### Two alerts to enable on day one

1. **Unstamped edits** — `tool:"editFiles" AND NOT req_ids:*` — fires when an agent edited code without a REQ-ID stamp. Either a bug or a policy bypass; investigate immediately.
2. **Cost spike** — sum of `cost_usd` over a rolling 1h window above your threshold. Catches runaway loops and bad prompts early.

### Capacity / cost notes

Audit events are tiny (~500 bytes each). A busy team running 200 sessions/day with ~50 events/session generates roughly 5 MB/day raw, < 100 MB/month after ES overhead. Single shard, single replica covers years before you think about scaling.

---

## Independent of the above

- **GitHub Copilot Enterprise audit logs** (if applicable): GitHub records every prompt/response/tool call at the org level. Use the audit-log API as a corroborating source — you have your own audit too, but the Enterprise log is the authoritative external record.
- **Hashes, not bodies**: `audit_log.py` hashes `--args` rather than storing them. Keeps the index small and avoids leaking source into the audit.
