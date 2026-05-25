---
name: scan-repo
description: "Use after discover-application has written .copilot/application.json. For each repo listed, detects languages, frameworks, build/test/lint/audit commands, package manager, layout, and existing conventions. Writes .copilot/context.json with one entry per repo. Runs once per session; downstream agents read context.json instead of re-discovering. Skip if context.json is < 24h old."
user-invokable: true
disable-model-invocation: false
allowed-tools: ['search', 'editFiles', 'runTasks']
---

# Scan repositories → `.copilot/context.json`

The goal: one compact, accurate snapshot every other agent reads instead of re-discovering. **Budget: ~30 seconds per repo, regardless of repo size.**

This skill is a thin router. The heavy lifting is in `scripts/scan_repo.py` — deterministic Python, no LLM tokens spent on manifest parsing.

## When to use

- After `discover-application` for a fresh session.
- After a major refactor that changes the stack.
- `.copilot/context.json` is missing or > 24h old.

## When NOT to use

- `.copilot/context.json` exists and is fresh → read it.
- The user is asking a non-code question.
- You only need one specific command — `cat .copilot/context.json | jq` is cheaper than re-scanning.

## Procedure

1. Read `.copilot/application.json`. Iterate over `repos[]`.
2. For each repo:
   - If `local_path` is set and exists, scan there.
   - Else, surface a one-line clone hint and skip that repo.
3. Invoke `scripts/scan_repo.py --root <local_path> --name <repo_name>` via the `scan:repo` task. The script:
   - Reads at most ~15 files per repo.
   - Emits one JSON object per repo on stdout.
4. After all repos scanned, write the combined `.copilot/context.json` per the schema in `references/context-schema.md`.
5. Print a 3-line summary per repo. No more.
6. Hand off.

## Token discipline (Karpathy: progressive disclosure)

- The LLM does **not** read manifests directly. The script does. The LLM consumes structured output only.
- The LLM does **not** narrate progress.
- Deep field-level details live in `references/context-schema.md`, loaded on demand. Not in the hot context.

## Output (high level)

```json
{
  "version": 2,
  "generated_at": "2026-05-22T10:00:00Z",
  "application": "payments-api",
  "repos": {
    "payments-api":          { "stack": {...}, "commands": {...}, "layout": {...}, "conventions": {...} },
    "payments-api-frontend": { "stack": {...}, "commands": {...}, "layout": {...}, "conventions": {...} }
  },
  "guardrails": { "no_install_without_adr": true, "no_eval_from_untrusted": true }
}
```

Full per-field schema → `references/context-schema.md`.

## Hard limits

- Max 15 files per repo.
- No source-code modifications. Only `.copilot/context.json`.
- No package installs.
- No invented commands. If a build/test isn't obvious, set `[]` and note in `summary`.

## Audit

`emit-audit`: `phase: start` before loop, one event per repo, `phase: end` after write.

## Example output to user

```
Application: payments-api (3 repos)
  · payments-api          .NET 8 + xUnit       build: dotnet build      test: dotnet test
  · payments-api-frontend Angular 17 + Jest    build: npm run build     test: npm test
  · payments-api-shared   .NET 8 (library)     build: dotnet build      test: dotnet test
Wrote .copilot/context.json. Handing off to Requirements Gatherer.
```
