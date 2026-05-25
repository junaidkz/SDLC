---
name: discover-application
description: "Use at the start of every session, before scan-repo. Asks the user for an application name, queries the configured service-catalog API (Backstage, ServiceNow, or custom JSON API) to resolve the application's repository list, and falls back to asking the user when no catalog is configured or the API returns no match. Writes the resolved list to .copilot/application.json. Runs once per session; subsequent runs read the cache."
user-invokable: true
disable-model-invocation: false
allowed-tools: ['editFiles', 'runTasks']
---

# Discover application + its repositories

Establishes **what we're working on** before any repo scanning happens. Output: `.copilot/application.json` with the application name, owner, and repo list. The `scan-repo` skill consumes this.

## When to use

- New session, no `.copilot/application.json` exists.
- User changes application focus mid-session.
- User passes `/discover-application` explicitly.

## When NOT to use

- `.copilot/application.json` exists and is < 7 days old → read it instead.
- User is asking a non-code question (e.g. "what does OWASP A03 mean") → no application context needed.
- The conversation is clearly about a single, already-loaded repo from prior context.

## Procedure (deterministic where possible)

1. **Ask the user the application name** (one question, no preamble):
   > *What application are we working on today?*

2. **Check for catalog config** at `.copilot/catalog.json`:
   - Exists → invoke `query_catalog.py` via the `discover:query-catalog` task.
   - Missing → skip to step 4 (manual mode).

3. **Query the catalog** via the script. Three outcomes:
   - **Hit**: script writes `.copilot/application.json` with repos. Confirm the list with the user: *"Found N repos for `<app>`: [...]. Confirm with 'go' or list corrections."*
   - **Miss** (404 / empty): tell the user *"`<app>` not found in catalog"*, fall through to step 4.
   - **Error** (5xx, auth, network): surface the error verbatim, fall through to step 4. Never silently retry.

4. **Manual fallback** — ask the user for the repo list:
   > *I'll need the repos manually. Paste one git URL per line, or local paths if already cloned. Reply 'done' when finished.*

   Then write `.copilot/application.json` directly via `editFiles` (no script needed for manual input — the LLM is the right tool here).

5. **Confirm + hand off**. Print the resolved application + repo count + a one-line per repo. Hand off to `scan-repo`.

## Output schema (`.copilot/application.json`)

See `templates/application.template.json` for the exact schema. Minimal valid output:

```json
{
  "version": 1,
  "generated_at": "2026-05-22T10:00:00Z",
  "application": {
    "name": "payments-api",
    "owner": "platform-team",
    "source": "backstage"
  },
  "repos": [
    {
      "name": "payments-api",
      "url": "https://github.com/acme/payments-api",
      "default_branch": "main",
      "local_path": null,
      "role": "primary"
    },
    {
      "name": "payments-api-frontend",
      "url": "https://github.com/acme/payments-api-frontend",
      "default_branch": "main",
      "local_path": null,
      "role": "supporting"
    }
  ]
}
```

`source` values: `backstage` | `custom` | `manual`. The Reviewer audits this — manually-entered repos are flagged for explicit user confirmation in the plan-approval gate.

## Catalog providers supported

Detailed in `references/catalog-providers.md`. Quick map:

| Provider | `.copilot/catalog.json.type` | Notes |
|---|---|---|
| Backstage | `backstage` | Default. Uses `/api/catalog/entities/by-name/component/<name>`. Bearer auth. |
| ServiceNow CMDB | `servicenow` | Maps `cmdb_ci_appl` → `cmdb_ci_app_server`. Basic auth. |
| Custom JSON | `custom` | Generic. You provide `url_pattern` + `response_path`. |
| None | (file absent) | Always falls back to manual. |

## Token discipline

- One question. Not three.
- No re-asking what the user already said.
- After the script runs, do **not** re-print its output verbatim — summarise in 3 lines.
- This skill emits exactly two audit events: `phase: start` (after the question is answered) and `phase: end` (after the file is written).

## Example session

```
Agent: What application are we working on today?
User:  payments-api
Agent: [runs discover:query-catalog]
       Found 3 repos for payments-api (source: backstage):
         · payments-api          (primary,    main)
         · payments-api-frontend (supporting, main)
         · payments-api-shared   (supporting, main)
       Confirm with 'go' or describe corrections.
User:  go
Agent: Wrote .copilot/application.json. Handing off to scan-repo.
       [→ scan-repo]
```
