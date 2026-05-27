# Copilot Agent Orchestrator v7 — Multi-Repo, Org-Owned

The two questions you asked, answered up front:

1. **"How do I add the orchestrator to each repo when an application spans multiple repos?"**
   You don't. The agents and skills live **once** at the organization level (in `<org>/.github-private`). They are visible to every repo in the org automatically. Each app repo only adds a tiny overlay (catalog config, `tasks.json` wiring, and its own `features/` + RTM).

2. **"Who maintains the main initiator / agents?"**
   The **platform / DevX team** owns the `.github-private` repo. App teams own their per-repo overlay. CODEOWNERS, branch protection, canary tests, and a versioning policy enforce the split. Updating the org agents is a normal PR with a `REQ-ORCH-NNN` of its own — the orchestrator's own ceremony applies to changes to itself.

## How GitHub actually loads org-wide agents

GitHub Copilot looks for custom agents in two places:

| Scope | Location | Discovered from |
|---|---|---|
| Repository | `<repo>/.github/agents/<name>.agent.md` | That repo only |
| **Organization** | `<org>/.github-private/agents/<name>.agent.md` | **Every repo in the org** |

Note the org path: it's `agents/` at the **root** of `.github-private`, not under `.github/`. Same for `skills/`, `instructions/`, etc. This bundle's `org-dot-github-private/` directory shows the exact layout to push to your `.github-private` repo.

## The three deliverable bundles

```
copilot-orchestrator-v7/
├── org-dot-github-private/      ← push this to <org>/.github-private (org-wide)
├── per-app-repo-overlay/        ← drop this into each application repo
└── governance/                   ← CODEOWNERS, branch protection, CI, canary apps
```

### `org-dot-github-private/` — push once, used everywhere

```
agents/                             # six agents, discovered org-wide
skills/                             # eight skills with scripts/ and references/
schemas/handoffs.schema.json
instructions/                       # security + token-budget, auto-applied everywhere
copilot-instructions.md             # root project-wide rules
scripts/                            # audit_log, ship_audit_to_es, enrich_audit_with_tokens, create_jira_from_feature
infra/                              # ES index template, Filebeat config, Kibana setup
docs/workflow.svg + workflow.md     # the diagram
.github/workflows/create-jira-from-feature.yml
README.md                           # owner guide for the platform team
```

### `per-app-repo-overlay/` — what each app repo needs

```
.copilot/
├── catalog.example.json    # copy to catalog.json and edit for your provider
├── context.template.json   # reference; the Initiator generates the real one
└── .gitignore              # keeps generated files out of git
.vscode/tasks.json          # wires the org scripts into runTasks
docs/
├── requirements.md         # REQ-ID index for THIS application
└── traceability.md         # RTM for THIS application
features/                   # BDD files for THIS application
README.md                   # setup guide for the app team
```

### `governance/` — platform team's operating manual

```
CODEOWNERS.example                       # who reviews what in .github-private
branch-protection.json                   # gh CLI input to lock down main
.github-workflows-validate-orchestrator.yml
                                         # CI that runs on every PR to .github-private
validators/
├── validate_agents.py                   # frontmatter check
└── validate_skills.py                   # frontmatter + length + format check
canary-apps/
└── multi-repo-flow/                     # smoke test for the multi-repo flow
    ├── application.json
    └── run-canary.sh                    # tested, passes
```

## Where things physically live — the table

| Artifact | Lives in | Owned by | Why |
|---|---|---|---|
| Agent definitions (`*.agent.md`) | `<org>/.github-private/agents/` | Platform team | Same persona everywhere |
| Skills (`SKILL.md`, `scripts/`, `references/`) | `<org>/.github-private/skills/` | Platform team (+ subject-matter co-owners) | Same conventions everywhere |
| Inter-agent schemas | `<org>/.github-private/schemas/` | Platform team | Breaking changes need versioning |
| Repo-wide instructions | `<org>/.github-private/copilot-instructions.md` and `instructions/` | Platform team + security team | Auto-applied to every interaction |
| Audit + Jira scripts | `<org>/.github-private/scripts/` | Platform team | Versioned alongside the agents that call them |
| Elasticsearch / Filebeat config | `<org>/.github-private/infra/` | Ops team | One audit pipeline for the org |
| Service-catalog config | **each app repo** `.copilot/catalog.json` | App team | Different apps may use different catalogs |
| VS Code task wiring | **each app repo** `.vscode/tasks.json` | App team | Needs to know where ORCH_HOME is on the local machine |
| `application.json`, `context.json` | **each app repo** `.copilot/*.json` (gitignored) | Generated per session | Per-session, not source-controlled |
| `features/` BDD specs | **each app repo** | App team + QA | Application-specific source of truth |
| `docs/requirements.md`, `docs/traceability.md` | **each app repo** (the primary one) | App team + security | Application-specific source of truth |
| `docs/adr/` | **each app repo** | App team + architecture | Application-specific decisions |
| Generated audit JSONL | local `~/.copilot/audit/` per developer | (operational) | Shipped to ES, not committed |

## Multi-repo data flow

When an application spans repos A, B, C:

1. The Initiator (org-wide agent) runs `discover-application` → asks the user for the app name → queries the catalog → writes `<primary-repo>/.copilot/application.json` listing A, B, C.
2. The Initiator runs `scan-repo` over each of A, B, C → writes a single `<primary-repo>/.copilot/context.json` with one entry per repo:
   ```jsonc
   {
     "version": 2,
     "application": "payments-api",
     "repos": {
       "payments-api":          { ... stack: csharp + aspnetcore ... },
       "payments-api-frontend": { ... stack: typescript + angular ... },
       "payments-api-shared":   { ... stack: csharp library ... }
     }
   }
   ```
3. The Planner reads `context.json.repos[*]` and produces a plan whose **Affected Surface** spans multiple repos — file paths qualified by repo (`payments-api-frontend/src/auth.ts`).
4. The Implementer edits across repos. Audit events carry the `repo` field per touched file.
5. The Reviewer reads the same `context.json`. The RTM in the primary repo accumulates rows that may reference files in any of A, B, C.
6. Jira-creation GHA runs on the primary repo's PR (the one with `.feature` files), creates one Jira issue covering all the cross-repo changes, references it from each repo's PR body via `Refs: PLAT-1234`.

The "primary" repo is the one with `features/` and `docs/requirements.md`. By convention it's the backend or main API repo; the application.json's `role: "primary"` field marks it. Frontend / shared-lib PRs in this flow reference the primary repo's REQ-ID and Jira key in commits, without owning the spec themselves.

## Ownership matrix

| Question | Answer |
|---|---|
| Who creates new agents? | Platform team, via PR to `.github-private` with a `REQ-ORCH-NNN` driving the change |
| Who creates new skills? | Anyone can propose; platform team approves via CODEOWNERS |
| Who can change `security.instructions.md`? | Platform team + security team (CODEOWNERS dual-owner) |
| Who can change the cost rate table in `enrich_audit_with_tokens.py`? | Platform team + finops |
| Who decides catalog provider per app? | App team, via their `.copilot/catalog.json` |
| Who owns the audit pipeline (ES, Filebeat, Kibana)? | Ops team — `infra/` directory |
| Who fixes the orchestrator when a Copilot release breaks it? | Platform team, treating it as a P1 |
| Who pays attention to Kibana cost dashboards? | Finops / engineering managers — feed into sprint planning |

## Version policy

| Change type | Allowed in minor version | Requires major version |
|---|---|---|
| Add a new skill | ✓ |   |
| Add a new agent | ✓ |   |
| Add an optional field to a schema | ✓ |   |
| Add a `When NOT to use` clarification | ✓ |   |
| Remove a skill | | ✓ |
| Rename a schema field | | ✓ |
| Change the default of a guardrail (`no_install_without_adr`, etc.) | | ✓ |
| Change an agent's model assignment | ✓ (announce in release notes) |   |
| Add a new audit event field | ✓ (ES mapping needs updating in lock-step) |   |
| Remove or rename an audit event field | | ✓ |

App repos consume by submodule (Option A), per-developer clone (Option B), or packaged install (Option C). Pin to a tag in regulated apps; track `main` in fast-moving ones.

## The orchestrator's own ceremony, applied to itself

Every change to `.github-private` follows the flow the orchestrator enforces on app code:

1. Open a PR with a new `features/<area>/<name>.feature` carrying `REQ-ORCH-NNN`. Scenarios describe the new agent/skill behaviour.
2. Jira-creation workflow attaches a Jira key.
3. CI (`validate-orchestrator`) runs:
   - YAML frontmatter validators on agents and skills.
   - Python compile + smoke tests.
   - Canary apps in `governance/canary-apps/` run end-to-end against the proposed change.
4. CODEOWNERS approval.
5. Tag on merge.

The platform team is the first user of every change — if it breaks the meta-flow, it doesn't ship.

## Operational SLAs (starting point — tune to your org)

| Event | Response |
|---|---|
| Critical security finding in agents/skills | Hotfix same day, all canaries re-run |
| Copilot release breaks an agent frontmatter | P1; pin Copilot version until fix; ETA 1 week |
| App team requests new skill | Triage in next sprint planning |
| Schema field rename request | Major version bump cycle; ~1 quarter notice to consumers |
| Kibana cost-spike alert | Investigate within 1 business day |

## TL;DR — what to do this week

1. Create `.github-private` in your org (Private). Push the contents of `org-dot-github-private/`.
2. Add `governance/CODEOWNERS.example` as `.github/CODEOWNERS` in the new repo. Replace placeholders.
3. Apply `governance/branch-protection.json` via `gh api`.
4. Drop `governance/.github-workflows-validate-orchestrator.yml` into `.github/workflows/validate-orchestrator.yml`.
5. In every application repo, drop the `per-app-repo-overlay/` files. Configure `catalog.json` if you have a catalog. Tell developers to set `ORCH_HOME`.
6. Open a Copilot Chat in any app repo → the org-wide agents are already in the agent dropdown. Pick `@orchestrator` and start.

That's it. The agents now span every repo in the org, and exactly one team owns updating them.
