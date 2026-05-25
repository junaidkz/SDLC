---
name: propose-adr
description: Use when a coding task seems to require a new dependency (npm/NuGet/pip/cargo) or a new architectural pattern. Writes a short ADR proposal to docs/adr/, asks the user to approve in chat, and pauses execution. Primarily used by the Implementer; do not install anything until the user explicitly approves.
user-invokable: true
disable-model-invocation: false
allowed-tools: ['search', 'editFiles']
---

# Propose an ADR before adding a dependency or pattern

The project rule is **no package installs without an ADR + explicit user approval in chat**. This skill produces the ADR and pauses.

## When to invoke

- The Planner's plan or your own discovery surfaces a new dependency.
- A non-trivial architectural change (new framework, new auth scheme, new storage backend) is needed.
- You're about to write a workaround that warrants documenting *why*.

## When NOT to invoke

- Adding a using/import for an already-installed package.
- Internal refactors with no external surface change.
- Bug fixes within an existing pattern.

## Decision tree (before writing the ADR)

1. Is there an existing dep in `package.json` / `*.csproj` that already solves this? → Use it. No ADR.
2. Is the dep tiny + transitive of something we already pull? → Still an ADR if it's a direct add. Be honest about it.
3. Has a similar ADR been proposed and rejected? → Find it in `docs/adr/`, address the rejection reasons, or pick a different approach.

## ADR template

File: `docs/adr/ADR-<NNNN>-<short-kebab>.md` where `NNNN` is the next available number (check `docs/adr/`).

```markdown
---
adr_id: ADR-0011
title: <decision in 6 words or fewer>
status: proposed     # proposed | accepted | rejected | superseded
requirements: [REQ-XXX-NNN]
jira: [PLAT-NNNN]
date: 2026-05-22
proposer: <agent: implementer | other>
---

## Context

<2–3 sentences. What problem are we solving? What in the current codebase is insufficient?>

## Decision

<1–2 sentences. The change being proposed. Name the package/pattern/framework specifically.>

## Alternatives considered

- **<alt 1>**: <why not — one line>
- **<alt 2>**: <why not — one line>
- **Do nothing**: <what we lose by not making this change>

## Consequences

- ✅ <positive consequence>
- ✅ <positive consequence>
- ⚠️  <negative or new risk>
- ⚠️  <ongoing cost — maintenance, upgrade cadence, license>

## Implementation impact

- New dependency: `<name>@<version>` (~`<size>` kB, license `<license>`)
- Files touched: `<rough estimate>`
- Tests added: `<rough estimate>`
- Run after install:
  - .NET: `dotnet list package --vulnerable --include-transitive`
  - Node: `npm audit --omit=dev`
  - Python: `pip-audit`

## Open questions

- <question for the user>
```

## After writing the ADR

1. Write the file via `editFiles`.
2. Emit an audit event (`emit-audit` skill) with `tool: propose-adr`, `tool-status: pending`.
3. Present the ADR to the user in chat with this exact ask:

> "I need to add `<package>@<version>` for `<REQ-ID>`. ADR drafted at `docs/adr/ADR-NNNN-<slug>.md`. Approve with 'install' to proceed, or 'reject' / 'alternative: <other>' to course-correct."

4. **Stop. Do not run any install command.** Wait for the user's reply.

## On user approval ('install')

1. Change ADR `status: proposed` → `status: accepted`.
2. Run the install command listed in `.copilot/context.json.commands.install`.
3. Immediately run the corresponding `audit` command. If `high`/`critical` advisories appear, REJECT the install and revert.
4. Reference the ADR ID in the commit message: `[REQ-XXX-NNN] add <package> (ADR-NNNN)`.

## On user rejection

1. Change ADR `status: proposed` → `status: rejected`.
2. Add a `## Rejection rationale` section with the user's reason.
3. Hand back to the Planner — the plan needs revision.
