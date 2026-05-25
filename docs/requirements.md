# Requirements

Source-of-truth index. Authored by the **Requirements Gatherer** agent. Every entry has a corresponding `.feature` file and a Jira ticket.

## ID convention

`REQ-<AREA>-<NNN>` where `AREA` is the bounded context (e.g. `AUTH`, `LINEAGE`, `BILLING`).

## Status lifecycle

`draft` → `approved` → `in-progress` → `done` → (optionally) `deprecated`

Only `approved` and `in-progress` are eligible for the Planner.

---

## REQ-AUTH-014
- **Status:** in-progress
- **Area:** Authentication
- **Statement:** Refresh tokens rotate on every use; the previous token is invalidated within 5 seconds.
- **Jira:** PLAT-1234
- **Feature file:** `features/authentication/refresh-token-rotation.feature`
- **Acceptance criteria:**
  - AC-1: New token issued on each refresh; old token rejected on subsequent use.
  - AC-2: Reuse of an invalidated token logs an audit event with severity `WARN` (carries user id + source IP).
  - AC-3: p99 rotation latency under 5s at 50 RPS for 60s.
- **Linked ADRs:** ADR-0011

---

## REQ-LINEAGE-007
- **Status:** in-progress
- **Area:** Knowledge Fabric
- **Statement:** Field-level mapping ingestion accepts CSV and writes nodes/edges to Apache AGE idempotently.
- **Jira:** PLAT-1289
- **Feature file:** `features/knowledge-fabric/csv-ingest.feature`
- **Acceptance criteria:**
  - AC-1: Re-running the same CSV produces zero new nodes/edges (idempotency).
  - AC-2: Malformed rows skipped with structured log; ingestion continues.
  - AC-3: Summary row count emitted as `{ accepted, skipped, errors }`.
- **Linked ADRs:** ADR-0019

---

<!-- Add new requirements above this line. Do not renumber existing IDs. The Requirements Gatherer appends here. -->
