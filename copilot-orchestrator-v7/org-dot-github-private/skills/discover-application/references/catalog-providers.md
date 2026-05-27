# Catalog Providers — Reference

Loaded only when the user is configuring or troubleshooting catalog integration. Not part of the agent's hot context.

## Configuration file

`.copilot/catalog.json` — checked in to the repo (no secrets) and committed by whoever wires up the integration.

```json
{
  "type": "backstage",
  "url": "https://backstage.acme.internal/api/catalog",
  "auth": {
    "type": "bearer",
    "token_env": "BACKSTAGE_TOKEN"
  },
  "repo_field_map": {
    "name": "name",
    "url": "url",
    "default_branch": "defaultBranch",
    "role": "role"
  }
}
```

Auth secrets live in env vars, not in this file.

## Provider: `backstage`

Endpoint: `GET {url}/entities/by-name/component/{app_name}`

We read:
- `spec.source.location` (canonical) — the primary git URL.
- `metadata.annotations["backstage.io/source-location"]` — alternative location.
- `metadata.annotations["github.com/project-slug"]` — derive a URL from `slug`.
- `spec.subcomponentOf` — supporting repos (rare, but supported).

Auth: bearer token via `BACKSTAGE_TOKEN`. Most installations also accept a service-account PAT.

## Provider: `custom`

For in-house catalogs. Configure with two extra fields:

```json
{
  "type": "custom",
  "url_pattern": "https://catalog.acme.internal/v2/apps/{app}/repositories",
  "response_path": "data.repositories",
  "auth": { "type": "bearer", "token_env": "CATALOG_TOKEN" },
  "repo_field_map": {
    "name": "repo_name",
    "url": "git_url",
    "default_branch": "main_branch",
    "role": "tier"
  }
}
```

`{app}` is URL-encoded and substituted into `url_pattern`. `response_path` walks dotted keys into the JSON response to find the array of repo entries. `repo_field_map` projects each entry to our schema.

## Provider: `servicenow` (planned, not yet implemented)

For ServiceNow CMDB users, the mapping table is roughly:
- `cmdb_ci_appl` (Application) → `cmdb_ci_business_app_repository` (Repository)
- Join on `appl_sys_id`.

The query is more elaborate than a single REST call; would need a separate script. Not implemented in v5.

## Provider: `manual` / absent

If `.copilot/catalog.json` is missing or `type: manual`, the skill prompts the user directly. This is the default for unconfigured repos and works fine for small teams.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `missing env: BACKSTAGE_TOKEN` | Token not exported | `export BACKSTAGE_TOKEN=...` in your shell |
| `HTTP 401` | Token invalid/expired | Regenerate via Backstage UI |
| `HTTP 404` | App name doesn't match catalog | Check the canonical name in Backstage; case-sensitive |
| Repos returned but no URLs | `repo_field_map.url` points to wrong field | Inspect catalog response JSON; update the map |
| Script exits 2 with no detail | Check stderr; never silently retried by the skill | — |

## Why a script, not the LLM

Three reasons (Karpathy-aligned):

1. **Deterministic**: same input → same output. The LLM might paraphrase, miss a field, or hallucinate an extra repo. The script is exact.
2. **Cheap**: this is JSON parsing and a single HTTP call. No tokens spent on something `urllib` does in 100ms.
3. **Auditable**: the script's stdout/stderr appears verbatim in the audit log; the LLM's narration of the same operation would be paraphrased and noisier.

The LLM's role is *only* to ask the user the application name, run the script, and translate failures into a friendly fallback prompt.
