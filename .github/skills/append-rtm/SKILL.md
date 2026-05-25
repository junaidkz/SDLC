---
name: append-rtm
description: Use after the Reviewer approves a change. Appends one row per REQ-ID/AC pair to docs/traceability.md, linking REQ-ID → AC → feature scenario → implementation files → tests → commit → PR. Primarily used by the Implementer as the final step before committing.
user-invokable: true
disable-model-invocation: false
allowed-tools: ['search', 'editFiles', 'changes']
---

# Append rows to the Requirements Traceability Matrix

The RTM (`docs/traceability.md`) is the append-only ledger that makes any REQ-ID queryable end-to-end. Add rows here **only after** the Reviewer returns `STATUS: APPROVED`.

## Schema

```
| REQ-ID | Jira | AC | Feature scenario | Implementation | Tests | Commit | PR | Date | Status |
```

## One row per (REQ-ID, AC) pair

If a change satisfies AC-1, AC-2, AC-3 of REQ-AUTH-014, append three rows. This makes per-AC coverage trivial to query.

## Field rules

| Field | Format | Notes |
|---|---|---|
| REQ-ID | `REQ-AUTH-014` | Plain text, matches `docs/requirements.md`. |
| Jira | `PLAT-1234` | The real key (the GHA workflow has already replaced `pending`). |
| AC | `AC-1` | Single AC per row. |
| Feature scenario | `` `<file>:@<TAG>` `` | Backtick-quoted. `<file>` is the path under `features/`; `<TAG>` is the scenario tag. |
| Implementation | `` `path/to/file.cs` `` | Comma-separated when multiple files. Backtick-quoted paths. |
| Tests | `` `tests/.../FooTests.cs` `` | Backtick-quoted paths. |
| Commit | `e4f5g6h` | Short SHA. Pull from `git rev-parse --short HEAD` after committing the implementation. |
| PR | `#156` | The PR number, hash-prefixed. |
| Date | `2026-05-22` | ISO date. |
| Status | `in-progress` / `done` | `done` only when **all** ACs of the REQ-ID have rows AND the PR is merged. |

## Idempotency

Do not edit historical rows. If a previously-recorded row needs correction:

1. Add a new row with the corrected data and `Status: superseded-by-<new-commit-sha>` in a leading comment line above the table — never overwrite.
2. Add the new replacement row below.

This keeps the audit trail intact for compliance.

## Procedure

1. Read the current `docs/traceability.md`.
2. For each `(REQ-ID, AC-N)` pair satisfied by this change, construct the row using fields gathered from:
   - REQ-ID + AC: from the `.feature` file frontmatter and scenario tags.
   - Implementation: the diff scope (files changed by your edits in this loop).
   - Tests: new or updated test files.
   - Commit SHA: run after `git commit` so the SHA exists.
   - PR number: from the current branch's open PR (or `<pending>` if not yet opened).
3. Append rows immediately above the trailing `<!-- Append new rows above this line. -->` comment.
4. Save with `editFiles`.
5. Emit an audit event (`emit-audit` skill) with `tool: append-rtm`, `tool-status: ok`, `files: [docs/traceability.md]`, `req-ids: [...]`.
6. Commit the RTM update as part of the same commit as the code change (`git add docs/traceability.md` before `git commit`).

## CI gate

`scripts/check-traceability.ps1` (configured separately in CI) verifies on every PR:

- Every `approved`/`in-progress` REQ-ID has at least one row.
- Every AC defined in the linked `.feature` file has a row.
- Every commit on the PR branch has a `[REQ-ID]` prefix.

If your row append is missing or malformed, CI fails and the PR is blocked.
