# Angular Migration Kit — Agents & Skills for Claude Code and GitHub Copilot

For migrating an ASP.NET MVC frontend (with runtime-generated HTML from DB/WCF data) to Angular 21, with WCF being replaced by Web API/REST.

## Install
Copy both the `.claude/` and `.github/` folders into the root of the repo you work in (ideally a workspace that contains, or can read, both the legacy MVC solution and the Angular boilerplate).

**Claude Code**: reads `.claude/agents/` and `.claude/skills/` automatically; verify with `/agents`.

**GitHub Copilot (targeting Claude Sonnet)**: reads the same `.claude/skills/` automatically (Agent Skills support). The `.github/agents/` folder contains the same six agents in Copilot's custom-agent format — select them from the agent picker (VS Code agent mode / Copilot CLI / cloud agent). Note Copilot runs one custom agent per session rather than auto-delegating between them, so switch agents as you move through the workflow steps.

The two agent folders have identical instructions — edit both if you change one (only the frontmatter differs).

## What's inside

**Agents** (subagents you can invoke by name or that Claude delegates to):
| Agent | Role |
|---|---|
| `mvc-inventory-analyzer` | Maps the legacy app: routes, views, WCF ops, and every runtime HTML-generation hotspot |
| `api-contract-designer` | Designs REST endpoints, DTOs, TS interfaces, and the page-metadata JSON schema |
| `dynamic-renderer-engineer` | Builds the Angular component registry + metadata-driven renderer |
| `angular-component-migrator` | Ports one view/feature at a time into your boilerplate |
| `migration-verifier` | Parity-checks each migrated feature against the legacy behavior |
| `legacy-js-migrator` | Inventories custom JS (drop/replace/port) and ports business logic to typed TS/services |

**Skills** (knowledge Claude consults while working):
| Skill | Covers |
|---|---|
| `angular21-conventions` | Standalone, signals, new control flow, typed reactive forms, testing |
| `mvc-to-angular-mapping` | Razor/ViewBag/DataAnnotations/jQuery → Angular translation table |
| `dynamic-html-migration` | The core pattern: server-generated HTML → metadata + component registry |
| `wcf-to-rest-mapping` | Contracts → endpoints, DTOs → TS, FaultContract → problem+json |

## Suggested workflow
1. `Use the mvc-inventory-analyzer agent to map the legacy app` → produces `docs/migration/inventory.md` + `dynamic-html-map.md`.
2. `Use the api-contract-designer agent for the <area> feature` → endpoint specs, TS models, `page-metadata.schema.json`.
3. `Use the legacy-js-migrator agent to inventory and port shared custom JS` (validators/formatters land in shared/ before features need them).
4. `Use the dynamic-renderer-engineer agent to scaffold the renderer and the first field types`.
5. Per feature, in order of the inventory: `angular-component-migrator` → `migration-verifier`. Repeat.
6. Everything writes traceable artifacts under `docs/migration/` so progress is auditable.

## Working within Copilot's context limits
The agents are written to run in small, resumable slices — important in VS Code Copilot where sessions have tighter context than Claude Code:
- **Inventory runs per area**: first run only builds `docs/migration/_checkpoint-inventory.md` (the area list); each later run deep-scans one area. Prompt: `Run the mvc-inventory-analyzer agent for the next pending area`.
- **State lives on disk**: every agent reads/writes `docs/migration/*` checkpoints, so you can end a session anytime and resume fresh — nothing depends on chat history.
- **One feature per session** for migrate/verify steps; start new chats liberally rather than letting one session grow.
- Commit `docs/migration/` to git — it's the coordination layer between agents, sessions, and tools.

## Tune before first run
- If your Angular boilerplate has strong opinions (state library, folder layout, UI kit), add a short `.claude/skills/boilerplate-conventions/SKILL.md` describing them — the agents are instructed to defer to boilerplate conventions.
- If the Web API is built by another team, trim `api-contract-designer` to "specify only" (it already leans that way).
- Adjust the metadata schema example in `dynamic-html-migration` once you've seen your real dynamic-html-map — then freeze it as `page-metadata.schema.json`.
