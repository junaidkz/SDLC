---
name: dynamic-html-migration
description: The core pattern for replacing MVC views whose HTML is generated at runtime from DB/service data. Use whenever encountering Html.Raw, TagBuilder, StringBuilder-built markup, server-returned HTML fragments, or any page whose fields/sections are decided by data — and whenever designing or extending the page-metadata JSON or the Angular component registry/renderer.
---

# Dynamic HTML → Metadata-Driven Rendering

## The rule
The legacy app decides page structure on the server and ships **HTML**. The new app ships **metadata** (JSON describing structure) and Angular renders it through a **component registry**. Never port runtime-generated HTML by injecting it (`[innerHTML]`) — you lose bindings, events, forms integration, type safety, and you inherit sanitization problems.

## Target architecture
```
DB / service data
      │
Web API composes PageDefinition JSON  (api-contract-designer owns the schema)
      │
Angular DynamicPageComponent
      ├─ builds FormGroup from field metadata
      ├─ walks sections/fields
      └─ ComponentRegistry: type → standalone component
              ├─ 'text'     → TextFieldComponent
              ├─ 'dropdown' → DropdownFieldComponent
              ├─ 'grid'     → GridComponent
              └─ 'section'/'tabs' → layout components (recurse)
```

## Metadata schema baseline (adapt, then freeze in page-metadata.schema.json)
```jsonc
{
  "schemaVersion": 1,
  "pageId": "customer-detail",
  "title": "Customer Detail",
  "sections": [{
    "id": "main", "type": "section", "label": "Details", "columns": 2,
    "children": [{
      "id": "status", "type": "dropdown", "label": "Status",
      "binding": "status",                       // key in the data payload / form
      "options": { "url": "/api/lookups/status" }, // or inline "items": [...]
      "validation": { "required": true },
      "rules": [{ "effect": "visible", "when": { "field": "kind", "eq": "active" } }]
    }]
  }],
  "actions": [{ "id": "save", "type": "submit", "label": "Save", "endpoint": "/api/customers/{id}" }]
}
```
Data and structure travel separately: `GET .../definition` (or embedded) + `GET .../data`. Cache definitions; data is per-entity.

## Extraction procedure (per legacy generator)
1. Read the C# that builds the HTML. List every element/attribute it can emit and every condition that changes output.
2. Each *kind* of emitted control → one registry `type`. Each condition → a metadata `rules` entry or an API-side decision (prefer API-side when it depends on server-only data like permissions).
3. Inline `onclick`/data-attributes → declarative `actions` metadata.
4. Validation attributes (`data-val-*`) → `validation` metadata → Reactive Forms validators.
5. Confirm with a golden test: render the Angular page from the new metadata and diff *behavior* (fields present, states, validation) against the legacy page for 2–3 representative records, including edge-case records that trigger the rarest branches.

## Renderer rules (dynamic-renderer-engineer implements)
- Registry is data (`Map<string, Type<FieldComponent>>` + provider registration), extended by registration only.
- Unknown `type` → loud dev-mode error + visible placeholder. Silence is how fields go missing.
- Rules engine: pure functions over form value → `{visible, disabled, required}` signals per field. No `eval`, no `Function()` — the rule vocabulary is a closed set defined in the schema.
- Recursive layout: sections/tabs/grids receive `children` metadata and re-invoke the renderer.

## The one innerHTML exception
Genuinely *authored* rich content (CMS blurbs, help text written as HTML in the DB) may use `[innerHTML]`. Angular sanitizes it (scripts/event handlers stripped). `bypassSecurityTrustHtml` only for trusted, non-user-editable sources, with a comment explaining why. Generated *structure* never qualifies.

## Smells that mean you're doing it wrong
- A per-page `switch` on field type inside a template → should be registry lookup.
- Copying `<div class="form-group">…` strings from C# into a TS string → stop, extract metadata.
- Page-specific renderer forks → the schema is missing a property; extend the schema (bump `schemaVersion`), don't fork.
