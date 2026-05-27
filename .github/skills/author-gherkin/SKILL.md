---
name: author-gherkin
description: "Use when creating or editing a .feature file in features/. Encodes the Gherkin/BDD authoring conventions for this repo, including frontmatter, REQ-ID/AC-N tagging, scenario structure, and the jira creation handoff to the Requirements Gatherer's jira:create-from-pending task. Primarily used by the Requirements Gatherer."
user-invokable: true
disable-model-invocation: false
---

# Author a Gherkin feature file

`.feature` files are the executable source of truth. Every scenario maps to at least one test; the Reviewer enforces this.

## When to use
- The Requirements Gatherer is authoring a new `.feature` file from user input.
- A user invoked `/author-gherkin` explicitly to format an existing draft.
- An existing `.feature` file needs scenarios added (without changing the REQ-ID — that belongs with the Requirements Gatherer).

## When NOT to use
- The user is editing prose docs (README, ADR) — those have their own templates.
- The feature already exists with the right scenario tags and no behaviour change is requested.
- The user is asking for a code change against an existing REQ-ID → the Planner runs, not this skill.

## File location

`features/<area>/<short-kebab-name>.feature`

`area` matches the REQ-ID area (`features/authentication/` for `REQ-AUTH-*`).

## Frontmatter (mandatory)

Gherkin does not support YAML frontmatter natively. Use a leading HTML-style comment block:

```gherkin
# ---
# req_id: REQ-AUTH-014
# jira: pending            # Requirements Gatherer replaces this via jira:create-from-pending
# status: approved          # draft | approved | in-progress | done | deprecated
# area: Authentication
# created: 2026-05-22
# owner: <team-or-handle>
# ---
```

**Set `jira: pending` for new files.** Do not invent a Jira key — Requirements Gatherer runs `jira:create-from-pending` and writes the real key back.

## Feature block

```gherkin
Feature: <short title — what behaviour this covers, not how>
  As a <actor>
  I want <intent in user language>
  So that <business outcome>
```

The narrative under `Feature:` is the elevator pitch. Keep it three lines.

## Background (optional)

Use for preconditions every scenario shares. Do not put assertions here — only `Given` steps.

```gherkin
  Background:
    Given the user is authenticated
    And the user holds a refresh token "T1"
```

## Scenarios

Each scenario gets exactly two tags: `@<REQ-ID>` and `@AC-<N>`.

```gherkin
  @REQ-AUTH-014 @AC-1
  Scenario: Successful rotation issues a new token and invalidates the old
    When the client POSTs T1 to /auth/refresh
    Then the response contains a new refresh token "T2"
    And subsequent use of T1 returns 401
```

- Scenario name is the AC, restated as a complete sentence. The Reviewer compares this to the AC list in `docs/requirements.md`.
- `Given/When/Then/And/But` steps should be **observable** (an HTTP call, a UI action, a queryable state) — not internal mechanics.
- One `When` per scenario. If you need two, split the scenario.
- Avoid "should" / "must" — write the observable fact in present tense.

## Scenario Outline (use sparingly)

For data-driven cases:

```gherkin
  @REQ-AUTH-014 @AC-1
  Scenario Outline: Rotation rejects invalid tokens
    When the client POSTs "<token>" to /auth/refresh
    Then the response is <status>

    Examples:
      | token       | status |
      | expired-T   | 401    |
      | tampered-T  | 401    |
      | unknown-T   | 401    |
```

Each example row counts as a separate AC verification — make sure each row's intent is in `requirements.md`.

## What to avoid

- ❌ UI implementation details (`When the user clicks the blue button on the top-right`) → write what the user accomplishes, not how the pixels look.
- ❌ Database-level steps (`Then row in users_table has updated_at >= now()`) → assert through the public API.
- ❌ Conjunctions in step names (`When the user logs in and updates profile`) → split into two `When`s or one `When` + one `And`.
- ❌ Scenarios without `@REQ-ID @AC-N` tags → Reviewer rejects.
- ❌ Invented Jira keys in frontmatter.

## Output protocol for the Requirements Gatherer

1. Draft the file and present its full content.
2. Append the new REQ-ID block to `docs/requirements.md` with `Jira: pending`.
3. Ask the user: *"Confirm this matches your intent. Reply 'go' to hand off to the Planner."*
4. Requirements Gatherer then runs `jira:create-from-pending` and confirms both files now carry the created Jira key.
