# Project-wide Copilot Instructions

These rules apply to **every** Copilot interaction in this repo. They are inherited by every custom agent and sit above agent prompts.

Supplemental instruction files (auto-applied):
- `.github/instructions/security.instructions.md` — prompt-injection + vulnerability rules.
- `.github/instructions/token-budget.instructions.md` — token-frugality rules.

## Source of truth (in order of precedence)

1. **Jira ticket** — the canonical record. Has the business intent and approval state.
2. **`.feature` file** in `features/` — the executable specification (Gherkin BDD). Frontmatter links it to the Jira issue key and REQ-ID.
3. **`docs/requirements.md`** — index of REQ-IDs with metadata (status, area, links to Jira + feature file).
4. **`docs/traceability.md`** — append-only ledger linking REQ-ID → AC → file → test → commit → PR.

**A change anywhere in 2–4 requires a corresponding update to 1.** If a user request would alter behaviour described in a `.feature` file or Jira ticket, stop and hand back to the **Requirements Gatherer** agent — never patch around the source of truth.

## ID + stamping convention

- REQ-IDs: `REQ-<AREA>-<NNN>` (e.g. `REQ-AUTH-014`).
- Jira keys: `<PROJ>-<NNN>` (e.g. `PLAT-1234`).
- Every commit, PR title, code docstring, and test name carries the REQ-ID(s). PRs additionally carry the Jira key in the body using `Refs: PLAT-1234`.
- New code: docstring tag `@req REQ-AUTH-014` and `@jira PLAT-1234`.
- New tests: REQ-ID embedded in name or `Trait` attribute.

## Hard rules

1. **No package installs without an ADR.** Adding a npm/NuGet/pip/cargo dependency requires an `docs/adr/ADR-<NNNN>.md` referencing the REQ-ID and explicit user approval in chat. The Implementer agent stops and asks; it never auto-installs.
2. **No work without a REQ-ID + Jira key.** Either point to an existing one or run the Requirements Gatherer first.
3. **The Planner is read-only.** It cannot edit files or run commands. If it produces edits, that is a bug — reject the output.
4. **Cross-model review is mandatory.** The Reviewer runs on a different model family than the Implementer.
5. **All agent actions are audited.** See `docs/traceability-architecture.md` for the audit pipeline. Every tool call lands in the JSONL session log.

## Workflow contract

```
Initiator → Requirements Gatherer → [USER APPROVAL] → Planner → [USER APPROVAL] → Implementer ⇄ Reviewer (loop) → Done
```

Two explicit human gates: after requirements, after plan. No surprises.

## Tech context (filled by Initiator at session start)

The Initiator agent writes `.copilot/context.json` with detected stack, build commands, test commands, package manager, and existing patterns. All downstream agents read this file instead of re-scanning the repo. **Do not duplicate that discovery work.**

## No MCP in this bundle

External integrations (Jira ticket creation, audit shipping) run as repo automation, not as MCP servers. Specifically:
- **Jira**: created during requirements authoring by the Requirements Gatherer via task `jira:create-from-pending`, which runs `scripts/create_jira_from_feature.py`.
- **Audit**: written to local JSONL by agents, shipped to Elasticsearch by Filebeat (or the bulk-POST script in `scripts/`), visualised in Kibana.

This keeps every external action auditable (it runs in CI or in a checked-in script) and removes the runtime dependency on MCP server availability.
