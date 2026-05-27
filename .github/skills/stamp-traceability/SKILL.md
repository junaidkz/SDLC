---
name: stamp-traceability
description: Use when writing or amending any code, test, commit message, or PR title/body. Encodes the REQ-ID + Jira-key stamping conventions that link every artifact back to its requirement. Used primarily by the Implementer; also relevant whenever code is edited outside the standard agent flow.
user-invokable: true
disable-model-invocation: false
---

# Stamp REQ-ID + Jira key on every artifact

Every artifact carries the IDs that link it back to `docs/requirements.md` and to the Jira ticket. The Reviewer rejects any artifact missing its stamp.

## When to use
- The Implementer is writing or amending code, tests, commit messages, or PR titles/bodies tied to a REQ-ID.
- Retrofitting older code that predates the REQ-ID convention.
- The Reviewer needs the source of truth for what counts as a valid stamp.

## When NOT to use
- Pure formatting / whitespace changes with no semantic content.
- Refactors with no observable behaviour change AND no test changes.
- Generated code (auto-formatters, scaffolders) — exempt by convention.

## Conventions by artifact type

### Commit messages

```
[REQ-AUTH-014] Rotate refresh token on every use

Refs: PLAT-1234
```

- Subject: `[<REQ-ID>] <imperative summary, <72 chars>`
- Body MUST include `Refs: <JIRA-KEY>` on its own line (the GitHub Action also writes this to PR body).
- Multiple REQ-IDs: comma-separated inside the brackets, multiple `Refs:` lines.

### PR titles

```
[REQ-AUTH-014] Refresh-token rotation
```

PR body must include `Refs: PLAT-1234` somewhere (the workflow appends this automatically when missing).

### C# / .NET — class, method, or record

```csharp
/// <summary>
/// Rotates a refresh token, invalidating the previous one.
/// </summary>
/// <remarks>
/// @req REQ-AUTH-014
/// @jira PLAT-1234
/// </remarks>
public Task<RefreshTokenPair> RotateAsync(string oldToken, CancellationToken ct) { ... }
```

For internal helpers, a single-line XML doc with the tags is sufficient.

### TypeScript / Angular — class, function, or component

```ts
/**
 * Rotates the user's refresh token.
 *
 * @req REQ-AUTH-014
 * @jira PLAT-1234
 */
export async function rotateRefreshToken(old: string): Promise<TokenPair> { ... }
```

### Tests — xUnit

```csharp
[Fact]
[Trait("req", "REQ-AUTH-014")]
[Trait("jira", "PLAT-1234")]
[Trait("scenario", "@AC-1")]
public async Task RotateToken_ValidT1_IssuesT2AndRejectsT1() { ... }
```

### Tests — Jest / Vitest

```ts
describe('@REQ-AUTH-014 @AC-1 — refresh token rotation', () => {
  it('issues a new token and invalidates the old', async () => { ... });
});
```

### Tests — pytest

```python
import pytest

@pytest.mark.req("REQ-AUTH-014")
@pytest.mark.jira("PLAT-1234")
@pytest.mark.scenario("@AC-1")
def test_rotate_token_issues_new_and_rejects_old():
    ...
```

(Register the markers in `pyproject.toml` to silence warnings.)

### ADRs and design docs

YAML frontmatter:

```markdown
---
adr_id: ADR-0011
title: Refresh-token rotation strategy
status: accepted
requirements: [REQ-AUTH-014]
jira: [PLAT-1234]
date: 2026-05-22
---
```

## Multiple REQ-IDs

A single change may satisfy multiple requirements:

```csharp
/// @req REQ-AUTH-014, REQ-AUDIT-003
/// @jira PLAT-1234, PLAT-1241
```

Commit: `[REQ-AUTH-014, REQ-AUDIT-003] ...`

## What the Reviewer checks

- Every new public symbol has `@req` + `@jira` tags.
- Every new test has the REQ-ID embedded (Trait, describe prefix, or pytest marker).
- Every commit on the PR branch has the `[REQ-ID]` prefix.
- Every PR body contains a `Refs:` line.

If any of these fail, the Reviewer returns `STATUS: REJECTED` with severity `blocking`. No exceptions.
