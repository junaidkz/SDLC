# Copilot Agent Orchestrator v5 — Karpathy-aligned, multi-repo, progressive disclosure

Drop-in bundle for VS Code GitHub Copilot. Six agents, eight skills (with `references/` + `scripts/` subfolders for progressive disclosure), structured JSON-Schema handoffs between agents, multi-repo aware, two human gates, BDD-first requirements, Jira via GitHub Actions, full audit trail in Elasticsearch + Kibana. No MCP.

![Workflow diagram](docs/workflow.svg)

(Mermaid version: [`docs/workflow.md`](docs/workflow.md))

## What's new in v5

### Application + multi-repo discovery

Sessions now start with: *"What application are we working on today?"* The new **`discover-application`** skill:

1. Asks the user the app name.
2. Queries the configured service catalog (Backstage / ServiceNow / custom JSON API) for the repo list. Configuration: `.copilot/catalog.json` (template + example included). Auth via env vars.
3. Falls back to manual repo entry if no catalog is configured or the app isn't found.
4. Writes `.copilot/application.json`.

The **`scan-repo`** skill then iterates the resolved repos, scans each with a deterministic Python script, and writes a multi-repo `.copilot/context.json` (schema v2).

### Karpathy-aligned best practices (applied throughout)

| Principle | Implementation |
|---|---|
| **Progressive context disclosure** | Skills are routers; deep content in `references/` (loaded on demand). `references/owasp-top10-2026.md` and `references/catalog-providers.md` and `references/context-schema.md` are the patterns. |
| **Deterministic over LLM where possible** | Catalog queries: `scripts/query_catalog.py`. Repo scanning: `scripts/scan_repo.py`. Audit emit: `scripts/audit_log.py`. The LLM does interpretation, not parsing. |
| **Structured inter-agent interfaces** | `.github/schemas/handoffs.schema.json` — JSON Schemas for `RequirementsHandoff`, `PlanHandoff`, `ReviewVerdict`, `AuditEvent`. Reviewer rejects payloads that don't conform. |
| **Harness over prompt** | Two human gates + Reviewer⇄Implementer loop + CI gates (Jira creation, traceability check) + audit pipeline. The scaffold is more of the value than any single prompt. |
| **When-NOT-to-use sections** | Every skill has them. Skills bow out gracefully when not applicable. |
| **Avoid premature context saturation** | No skill body exceeds 130 lines. Edge cases live in references. |

### Anthropic skills best practices (applied)

- **Description as a precise trigger**: each skill's `description` includes the user-facing words that should activate it ("Use after `discover-application` has written…").
- **`scripts/`** for executable helpers (called via `runTasks`).
- **`references/`** for deep look-up material.
- **`templates/`** for canonical example outputs.
- **Concrete output examples** in every SKILL.md.
- **All skills < 500 lines** (the Anthropic ceiling).

## Layout

```
.copilot/
  catalog.example.json              # service-catalog config template (copy + edit)
  context.template.json
.github/
  copilot-instructions.md
  instructions/
    security.instructions.md
    token-budget.instructions.md
  agents/                           # six agent definitions (50–110 lines each)
    initiator.agent.md              # runs discover-application + scan-repo
    orchestrator.agent.md
    requirements-gatherer.agent.md
    planner.agent.md
    implementer.agent.md
    reviewer.agent.md
  skills/                           # eight skills, each with references/ and scripts/ as appropriate
    discover-application/
      SKILL.md
      scripts/query_catalog.py       # stdlib, deterministic catalog query
      references/catalog-providers.md
      templates/application.template.json
    scan-repo/
      SKILL.md
      scripts/scan_repo.py           # stdlib, deterministic single-repo scanner
      references/context-schema.md
    review-owasp/
      SKILL.md
      references/owasp-top10-2026.md
    stamp-traceability/SKILL.md
    propose-adr/SKILL.md
    append-rtm/SKILL.md
    author-gherkin/SKILL.md
    emit-audit/SKILL.md
  schemas/
    handoffs.schema.json             # JSON-Schema for every inter-agent payload
  workflows/
    create-jira-from-feature.yml
docs/
  requirements.md
  traceability.md
  traceability-architecture.md
  workflow.svg                       # main diagram
  workflow.md                        # Mermaid version
features/authentication/refresh-token-rotation.feature
infra/
  elastic-index-template.json
  filebeat.yml
  kibana-setup.md
scripts/                             # repo-root scripts (called by GHA + audit pipeline)
  create_jira_from_feature.py
  audit_log.py
  ship_audit_to_es.py
```

## Flow (one sentence)

User triggers → Orchestrator routes → Initiator asks the app name + scans repos (first run only) → Requirements Gatherer writes a `.feature` → **user gate 1** → Planner writes a read-only plan → **user gate 2** → Implementer ⇄ Reviewer loop until APPROVED → commit + PR → GitHub Action creates Jira and writes the key back → RTM updated → done. Every step emits a JSONL audit event → Filebeat → Elasticsearch → Kibana.

## Models

| Agent | Model | Why |
|---|---|---|
| Initiator | GPT-5 mini | Routing + script invocation; small model is correct and cheap. |
| Orchestrator | GPT-5 mini | Routing only. |
| Requirements Gatherer | GPT-5 | Decomposition of fuzzy intent is reasoning-heavy. |
| Planner | GPT-5 | Plan errors compound across loops. |
| Implementer | Claude Sonnet 4.5 | Strongest agentic coder. |
| Reviewer | o3 | Different family from Implementer → different blind spots. |

## Setup (one-time)

### Repo
1. Copy folders into your repo root.
2. Add a `.vscode/tasks.json` with tasks `audit:log`, `discover:query-catalog`, `scan:repo` that wrap the corresponding scripts.

### Service catalog (optional but recommended)
1. Copy `.copilot/catalog.example.json` → `.copilot/catalog.json`.
2. Set the catalog URL and auth env var name. Provide the token in your shell or VS Code env.
3. Without this file, the Initiator falls back to asking for repos manually — still works fine for small teams.

### GitHub
- Variables: `JIRA_BASE_URL`, `JIRA_PROJECT_KEY`, `JIRA_USER_EMAIL`.
- Secret: `JIRA_API_TOKEN`.

### Elasticsearch + Kibana
Follow `infra/kibana-setup.md` — index template, rollover alias, optional ILM, dashboard tiles + alerts.

### Each developer
Install Filebeat with `infra/filebeat.yml`, or schedule `scripts/ship_audit_to_es.py`.

## What's enforced

| Risk | Mitigation | Where |
|---|---|---|
| Working on the wrong repos | App-name → catalog API → confirmed repo list | `discover-application` skill |
| Prompt injection from fetched content | All untrusted; no instruction-following from data; no `runCommands` | `security.instructions.md`, agent tool sets |
| Unauthorised package installs | ADR + chat approval required | `propose-adr` skill |
| Secrets in code / logs | Forbidden; strict ES mapping; redaction processors | `security.instructions.md`, `elastic-index-template.json` |
| Untagged work | Reviewer rejects on missing stamps; CI gate | `stamp-traceability`, `review-owasp` |
| Wasted tokens | Cached context, narrow tools, scripts > LLM for parsing, single-shot plans | `token-budget.instructions.md`, agent frontmatter, scripts |
| Drift between Jira & feature | GHA is the only writer of Jira keys; idempotent on `pending` | `create-jira-from-feature.yml` |
| Lost agent action audit | JSONL per session → ES → Kibana with replay search | full audit stack |
| Unstructured handoffs | JSON-Schema for every payload | `.github/schemas/handoffs.schema.json` |

## Known limits

- Custom-agent handoffs are user-click-driven in VS Code (intentional — keeps gates explicit).
- GitHub.com cloud coding agent ignores `handoffs` and `model` frontmatter; this bundle is designed for IDE use.
- Skill discovery is by description match — write descriptions with the words you'd say in chat.
- Catalog provider support: Backstage + custom JSON. ServiceNow planned, not implemented.
- Scripts are stdlib-only Python; no `pip install` anywhere.
