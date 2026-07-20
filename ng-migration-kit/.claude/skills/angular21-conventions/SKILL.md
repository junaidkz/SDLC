---
name: angular21-conventions
description: Angular 21 coding conventions for this migration project — standalone components, signals, new control flow, inject(), zoneless-safe patterns, and testing defaults. Use whenever writing or reviewing ANY Angular code in this repo, even small edits, and especially when tempted to write NgModule/decorator-input/*ngIf-era code from older Angular habits.
---

# Angular 21 Conventions

Target: Angular 21, standalone-first. Before deviating, check what the boilerplate already does — boilerplate conventions win over this document except for the "never" items.

## Components
- Standalone only (default in v21 — do not write `standalone: true`, and never create NgModules for features).
- `changeDetection: ChangeDetectionStrategy.OnPush` on every component.
- `inject(Service)` in field initializers, not constructor parameters.
- Inputs/outputs via functions: `value = input.required<Foo>()`, `disabled = input(false)`, `saved = output<Foo>()`. Never `@Input()`/`@Output()` decorators.
- Queries via `viewChild()`/`contentChild()` signal queries.
- `host: { ... }` object over `@HostBinding`/`@HostListener`.

## Templates
- New control flow only: `@if/@else`, `@for (x of xs; track x.id)`, `@switch`, `@defer` for heavy below-the-fold content. Never `*ngIf`/`*ngFor`.
- `@for` always has a meaningful `track`.
- Bind to signals directly: `{{ user().name }}`. No `async` pipe gymnastics when a signal will do.
- `[class.x]`/`[style.x]` bindings over `ngClass`/`ngStyle`.

## State & data
- Component state = signals; derived state = `computed()`; side effects sparingly via `effect()` (prefer deriving over effecting).
- Server data: prefer the boilerplate's established pattern. Where free to choose: `HttpClient` in an injectable API service returning observables at the edge, converted to signals in components via `toSignal()` or the `resource`/`httpResource` APIs (note: still experimental — acceptable here, but wrap usage in the project's own data-access layer so churn is contained).
- Assume zoneless compatibility: no code that relies on Zone.js triggering change detection (e.g., mutating state in `setTimeout` and expecting the view to update without a signal write).

## Forms
- Reactive Forms, strictly typed (`FormGroup<{...}>`, `nonNullable` where the legacy field had defaults).
- Validators mirror legacy DataAnnotations; custom validators are pure functions in `shared/validators`.
- Signal Forms exist in v21 as experimental — do not adopt for the migration unless the team decides so explicitly; typed Reactive Forms are the stable path for dynamic form building.

## Routing
- `provideRouter` with feature routes files; lazy `loadComponent`/`loadChildren` everywhere.
- Functional guards/resolvers (`CanActivateFn`), `inject()` inside them.
- `withComponentInputBinding()` so route params arrive as `input()`s.

## Testing & tooling
- Use whatever runner the repo is configured with (v21 scaffolds Vitest by default; older boilerplates may still be on Karma/Jasmine or Jest — check package.json, don't assume).
- Specs assert behavior (rendered output, form state, emitted outputs), not implementation details.
- Run `ng lint` and a production build before declaring work done.

## Never
- `any` without a `// why` comment; prefer `unknown` + narrowing.
- Direct DOM access (`document.*`, `ElementRef.nativeElement` writes) where a binding works.
- Logic in constructors beyond field init.
- Barrel files that create circular imports.
