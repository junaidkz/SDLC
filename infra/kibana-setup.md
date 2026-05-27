# Kibana Setup for Copilot Audit

## 1. One-time Elasticsearch setup

```bash
# 1) Apply the index template (controls mapping for all rollover indices)
curl -k -u "$ELASTIC_USERNAME:$ELASTIC_PASSWORD" \
  -X PUT "$ELASTIC_URL/_index_template/copilot-audit" \
  -H 'Content-Type: application/json' \
  --data-binary @infra/elastic-index-template.json

# 2) Bootstrap the rollover alias
curl -k -u "$ELASTIC_USERNAME:$ELASTIC_PASSWORD" \
  -X PUT "$ELASTIC_URL/copilot-audit-000001" \
  -H 'Content-Type: application/json' \
  -d '{ "aliases": { "copilot-audit": { "is_write_index": true } } }'

# 3) (Optional) Apply an ILM policy named copilot-audit-ilm — hot 7d, warm 30d, delete 365d.
#    Adjust to your compliance window.
```

## 2. Kibana data view

Stack Management → Data Views → Create:

- **Name**: `copilot-audit`
- **Index pattern**: `copilot-audit-*`
- **Timestamp field**: `@timestamp`

## 3. Recommended dashboard tiles

Build these in Kibana → Dashboards → Create. Each is one Lens or aggregation visualisation.

| # | Tile | Type | Aggregation | Filter |
|---|---|---|---|---|
| 1 | **Sessions today** | Metric | Cardinality of `session_id` | last 24h |
| 2 | **Tool calls by agent** | Bar (vertical) | Count, x: `agent.keyword`, breakdown: `tool.keyword` | last 7d |
| 3 | ~~Tokens in/out by model~~ | — | Requires OTel join — see `token-usage-tracking.md`. Don't build from this index. | — |
| 4 | ~~Cost per REQ-ID~~ | — | Requires OTel join — see `token-usage-tracking.md`. Don't build from this index. | — |
| 5 | **Rejection loop count by REQ-ID** | Table | Count where `agent:"reviewer" AND tool_status:"rejected"`, group: `req_ids.keyword` | last 30d |
| 6 | **Average latency by agent** | Bar | Average of `latency_ms`, x: `agent.keyword` | last 7d |
| 7 | **Errors timeline** | Line | Count where `error:*`, x: `@timestamp` (auto interval) | last 30d |
| 8 | **Top files touched** | Table | Count, group: `files.keyword`, top 25 | last 30d |
| 9 | **Per-PR audit trail** | Table | Group: `pr_number`, `agent.keyword`, `tool.keyword`; sum latency_ms | filter on PR number |
| 10 | **Coverage check** | Saved search | All events where `req_ids.keyword: REQ-AUTH-014` (parameterise) | last 90d |

## 4. Saved searches (most-used)

- **"Trace one session"** — query: `session_id:"<paste>"`, sort by `@timestamp` asc. Gives the full step-by-step replay.
- **"All reviewer rejections this week"** — `agent:"reviewer" AND tool_status:"rejected" AND @timestamp >= now-7d`.
- **"Unstamped tool calls"** — `tool:"editFiles" AND NOT req_ids:*`. Should be empty; alerts mean the agent skipped tagging.

## 5. Alerting (Kibana Alerting / Watcher)

Two alerts worth configuring:

1. **Unstamped edits**: rule on the *Unstamped tool calls* search → notify Slack/Teams immediately. Indicates either a bug in the agents or a policy bypass attempt.
2. **Cost spike**: rule on sum of `cost_usd` over 1h > threshold → notify. Catches runaway loops.

## 6. Verifying end-to-end

Run a smoke session:

```bash
# Manually emit a test event
COPILOT_SESSION=smoke-$(date +%s) python scripts/audit_log.py \
  --agent initiator --model gpt-5-mini --phase end --tool codebase --tool-status ok

# Wait ~10s for Filebeat (or run the fallback shipper)
python scripts/ship_audit_to_es.py

# Check it landed
curl -s -k -u "$ELASTIC_USERNAME:$ELASTIC_PASSWORD" \
  "$ELASTIC_URL/copilot-audit/_search?q=session_id:smoke-*&size=1" | jq .
```

## 7. What gets logged (and what doesn't)

- ✅ Agent, model, tool, files touched, REQ-IDs, Jira keys, scenario tags, latency, errors, commit/branch/PR/actor.
- ❌ Token counts (`tokens_in`, `tokens_out`, `cost_usd`) are NOT populated by this pipeline. Copilot Chat in VS Code does not expose per-turn token counts to custom agents. For token tracking use the official paths described in `infra/token-usage-tracking.md` (enable OTel, or read CLI session-state, or use the GitHub Copilot Enterprise usage API).
- ❌ Prompts, completions, file contents, user messages. Explicitly redacted (`user_message_redacted: true`). Filebeat also drops `message`, `prompt`, `completion` fields as defence in depth.

If you need prompt-level inspection for a specific incident, enable it per-session via an env var, not globally.

## 8. Token enrichment — see separate guide

Earlier versions of this bundle shipped an `enrich_audit_with_tokens.py` script that assumed Copilot Chat wrote per-turn JSON logs to predictable paths. **That assumption was wrong** — those paths don't reliably exist with the expected schema. The script has been removed.

The correct approach is documented in `infra/token-usage-tracking.md`. Summary: enable Copilot's OTel export (the official path) and either write to a file (per-developer) or send to an OTLP Collector that fans out to Langfuse / Application Insights / Grafana (centralised). Join to this audit by `session_id` and `actor`.

