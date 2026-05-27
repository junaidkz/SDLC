# Per-App-Repo Overlay

What each application repository needs in order to use the org's Copilot orchestrator.

This is a *tiny* footprint — the actual agents, skills, and scripts live in `<org>/.github-private`. This overlay just provides the per-app data and wiring.

## What's here

```
.copilot/
├── catalog.example.json     # copy → catalog.json and edit for your catalog provider
├── context.template.json    # reference; the Initiator generates the real one
└── .gitignore               # keeps generated application.json + context.json + audit/ out of git

.vscode/
└── tasks.json               # wires the org scripts via $ORCH_HOME so skills can call them

docs/
├── requirements.md          # REQ-ID index for THIS application
└── traceability.md          # RTM for THIS application

features/                    # BDD .feature files for THIS application
└── authentication/refresh-token-rotation.feature   # example, delete if not relevant
```

## Setup (one-time per app repo)

1. **Drop these folders into your repo root.** They don't conflict with anything; `.vscode/tasks.json` can be merged with an existing one.

2. **Pick a wiring option** for reaching the org agents/scripts (full detail in the org repo's README; summary here):

   **Option A — Submodule** (simplest):
   ```bash
   git submodule add https://github.com/<org>/.github-private .copilot/orchestrator
   git submodule update --init --recursive
   # Then in .vscode/tasks.json, replace ${env:ORCH_HOME} with ${workspaceFolder}/.copilot/orchestrator
   ```

   **Option B — Per-developer clone** (recommended at scale):
   ```bash
   # Each developer does this once
   git clone https://github.com/<org>/.github-private ~/.copilot/orchestrator
   # And exports
   export ORCH_HOME=~/.copilot/orchestrator
   # (in .zshrc / .bashrc / Windows env vars)
   ```

   **Option C — Packaged tool**: install the org's `copilot-orch` CLI; change tasks to call `copilot-orch <command>`.

3. **Configure your service catalog** (optional but recommended):
   ```bash
   cp .copilot/catalog.example.json .copilot/catalog.json
   # Edit catalog.json to point at your Backstage / ServiceNow / custom catalog API
   ```
   Without a catalog config, the Initiator falls back to asking the user for the repo list. Both paths work.

4. **Set audit env (per developer)**:
   ```bash
   export COPILOT_AUDIT_DIR=~/.copilot/audit
   ```
   Optional — defaults to that path anyway.

5. **Run Copilot Chat → agent dropdown → select `@orchestrator`** to start. The agent is published org-wide from `.github-private` so it's already in the list.

## Why so little here

Because the architecture is intentionally lopsided:

- **Lots of stuff in the org repo** — agents, skills, scripts, schemas, instructions. One set, governed by the platform team, applies to every application.
- **A little stuff per app** — the data that varies (which features, which REQ-IDs, which catalog) and the wiring (tasks.json).

Trying to put agents in every app repo would mean N copies drifting apart. Trying to put requirements in the org repo would mean every app's source of truth lives in someone else's house. This split keeps each team owning what they should own.

## Updating

- **App-specific changes** (features, RTM, ADRs) — your normal PR flow in this repo.
- **Orchestrator changes** (new skill, new agent behaviour) — open a PR against `<org>/.github-private`. Platform team reviews. New version available everywhere after merge (Option A and B both pull on `main` by default; pin to a tag if you need stability).

## CODEOWNERS suggestion (per-app)

```
/.copilot/catalog.json    @your-team
/docs/requirements.md     @your-team
/docs/traceability.md     @your-team @your-org/security-team
/features/                @your-team @your-org/qa-team
/docs/adr/                @your-team @your-org/architecture-team
/.vscode/tasks.json       @your-team   # rare; usually doesn't change after setup
```

The point: requirements and traceability for this app are owned here, by this team. The agents that operate on them are owned upstream, by the platform team.
