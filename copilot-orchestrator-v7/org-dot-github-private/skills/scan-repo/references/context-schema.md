# `.copilot/context.json` — Field-Level Schema

Loaded only when troubleshooting context.json or implementing a new agent that consumes it. Not in the hot context of the scan-repo skill.

## Top-level

```jsonc
{
  "version": 2,                          // bump when shape changes; v1 was single-repo
  "generated_at": "<ISO-8601>",
  "application": "<name from application.json>",
  "repos": {                             // keyed by repo short name
    "<repo-name>": <PerRepoContext>,
    ...
  },
  "guardrails": <Guardrails>,            // common to whole app
  "automation": <Automation>             // CI workflows + audit shipping config
}
```

## `<PerRepoContext>`

```jsonc
{
  "name": "<repo-name>",
  "root": "<absolute local path>",
  "summary": "<≤ 80 char one-liner: lang + framework>",

  "stack": {
    "languages": ["csharp", "typescript", ...],
    "frameworks": ["aspnetcore", "angular", ...],
    "package_managers": ["nuget", "npm", ...],
    "runtime": ["dotnet-8", "node-20", ...]
  },

  "commands": {
    "install":          ["dotnet restore", "npm ci"],
    "build":            ["dotnet build --no-restore -c Release", "npm run build"],
    "test_unit":        ["dotnet test --no-build", "npm test -- --watch=false"],
    "test_integration": [],                  // empty = none detected; don't invent
    "lint":             ["dotnet format --verify-no-changes", "npm run lint"],
    "audit":            ["dotnet list package --vulnerable --include-transitive", "npm audit --omit=dev"]
  },

  "layout": {
    "src":      ["src/"],
    "tests":    ["tests/"],
    "frontend": ["web/"],
    "features": ["features/"],
    "docs":     ["docs/"]
  },

  "conventions": {
    "test_framework":    "xunit + dotnet",      // or "jest", "pytest", etc.
    "test_naming":       "MethodName_State_Expected; Trait('req','REQ-XXX-NNN')",
    "di_container":      "Microsoft.Extensions.DependencyInjection",
    "logging":           "Microsoft.Extensions.Logging + Serilog",
    "style":             "see .editorconfig"
  }
}
```

## `<Guardrails>`

```jsonc
{
  "no_install_without_adr": true,
  "no_eval_from_untrusted": true,
  "secrets_via": "Azure Key Vault | env vars | other"
}
```

## `<Automation>`

```jsonc
{
  "jira_creation":  ".github/workflows/create-jira-from-feature.yml",
  "audit_shipping": "infra/filebeat.yml",
  "audit_index":    "copilot-audit"
}
```

## Field semantics

| Field | Empty means | Reading agents should… |
|---|---|---|
| `commands.test_integration` | not detected | not assume integration tests exist |
| `conventions.test_framework` | not detected | ask the user before adding tests |
| `stack.runtime` | unknown | use system default |
| `layout.features` | no `features/` dir | the Requirements Gatherer creates it on first use |

## Versioning rule

When the shape changes, bump `version` and update this doc. Backwards-incompatible changes require a code change in every agent that consumes `context.json`. List of consumers:

- `Initiator` (writer)
- `Requirements Gatherer` (reader: `conventions`, `layout.features`)
- `Planner` (reader: `commands`, `conventions`, `layout`)
- `Implementer` (reader: all)
- `Reviewer` (reader: `commands.audit`, `conventions`)

## Why `repos` as an object, not array

Most downstream lookups are by repo name (`context.repos["payments-api"].commands.build`). An object keyed by name is O(1); an array forces a `find()` every time. The application.json keeps the ordered list; context.json keeps the indexed map.
