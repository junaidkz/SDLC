# Requirements Traceability Matrix

Append-only ledger. Updated by the **Implementer** only after the Reviewer approves a change. Never edit historical rows; supersede with a new row.

## Schema

| REQ-ID | Jira | AC | Feature scenario | Implementation | Tests | Commit | PR | Date | Status |

## Entries

| REQ-ID | Jira | AC | Feature scenario | Implementation | Tests | Commit | PR | Date | Status |
|---|---|---|---|---|---|---|---|---|---|
| REQ-AUTH-014 | PLAT-1234 | AC-1 | `refresh-token-rotation.feature:@AC-1` | `src/Auth/RefreshTokenService.cs` | `tests/Auth/RefreshTokenServiceTests.cs` | `e4f5g6h` | #156 | 2026-05-02 | in-progress |
| REQ-AUTH-014 | PLAT-1234 | AC-2 | `refresh-token-rotation.feature:@AC-2` | `src/Auth/RefreshTokenService.cs`, `src/Audit/AuditLogger.cs` | `tests/Auth/RefreshTokenAuditTests.cs` | `i7j8k9l` | #156 | 2026-05-03 | in-progress |
| REQ-LINEAGE-007 | PLAT-1289 | AC-1 | `csv-ingest.feature:@AC-1` | `src/Lineage/CsvIngestor.cs`, `src/Lineage/GraphWriter.cs` | `tests/Lineage/CsvIngestorIdempotencyTests.cs` | `m1n2o3p` | #163 | 2026-05-19 | in-progress |

<!-- Append new rows above this line. -->

## CI enforcement

`scripts/check-traceability.ps1` runs in CI and fails the build when:
- Any `approved` or `in-progress` REQ-ID in `docs/requirements.md` has zero rows here.
- Any AC defined in the linked `.feature` file has no row here.
- Any commit on the PR branch lacks a `[REQ-ID]` prefix.

This closes the loop end-to-end. See `docs/traceability-architecture.md` for the full audit pipeline (agent actions, code, requirements, Jira).
