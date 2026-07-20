---
name: mvc-to-angular-mapping
description: Translation table from ASP.NET MVC/Razor patterns to Angular 21 equivalents. Use whenever reading a .cshtml view, Razor helper, MVC controller, or ViewModel with the intent of porting it — including partial views, HtmlHelpers, ViewBag/TempData, DataAnnotations validation, filters, and view-embedded jQuery.
---

# MVC → Angular 21 Mapping

Translate behavior, not markup. Read the ViewModel + controller action first; the .cshtml is just one rendering of that data.

## Structure
| MVC | Angular 21 |
|---|---|
| Controller action returning View | Routed container component + API call for the page payload |
| ViewModel | TS interface (from api-contract-designer) + component signals |
| `_Layout.cshtml` | Shell/layout component with `<router-outlet>` |
| Partial view / `Html.Partial` | Child standalone component with `input()`s |
| Editor/Display templates | Registered field components in the dynamic renderer |
| `Html.Action` / child actions | Component that fetches its own data (or gets it from the parent payload) |
| `RenderSection` | Content projection (`ng-content`) or router child outlets |
| Areas | Feature folders + lazy route groups |

## Data flow
| MVC | Angular 21 |
|---|---|
| ViewBag / ViewData | Don't recreate. Route data, component `input()`s, or the page payload |
| TempData (flash after redirect) | Toast/notification service; or router state for one-shot data |
| Session-driven view logic | Explicit API-provided flags — surface as a decision, never hidden client state |
| `RedirectToAction` | `router.navigate` after the API call resolves |
| Query string binding | `withComponentInputBinding()` route/query param inputs |

## Forms & validation
| MVC | Angular 21 |
|---|---|
| `Html.BeginForm` + POST action | Reactive Form + API service call (no full-page post) |
| DataAnnotations (`[Required]`, `[StringLength]`, `[Range]`, `[RegularExpression]`) | `Validators.required/maxLength/min/max/pattern` — same rule, same message |
| `[Remote]` validation | Async validator calling the equivalent endpoint |
| `ModelState` errors | Map problem+json field errors onto `FormControl.setErrors` |
| Unobtrusive validation messages | `@if (control.touched && control.hasError(...))` blocks; centralize message text |
| AntiForgeryToken | Per auth design (JWT: not needed; cookie auth: `withXsrfConfiguration`) |

## View logic & scripts
| MVC | Angular 21 |
|---|---|
| Razor `@if/@foreach` | `@if` / `@for (…; track …)` |
| `Html.Raw(generatedHtml)` | STOP — this is dynamic-html-migration territory, not a template port |
| jQuery in the view (show/hide, cascading dropdowns, ajax) | Signals + bindings; cascading data via `computed`/API calls on value changes |
| `@section Scripts` | Component logic; third-party init in `afterNextRender()` |
| Url.Action in JS | Typed API service methods |

## Cross-cutting
| MVC | Angular 21 |
|---|---|
| `[Authorize(Roles=…)]` | `CanActivateFn` guard checking the auth service; hide-and-guard, never hide-only |
| Action filters (logging, culture) | `HttpInterceptorFn` / route guards |
| `HandleError` | Global `ErrorHandler` + error interceptor |
| .resx localization | The boilerplate's i18n approach — reuse resource keys where possible |

## Traps
- Razor renders with server state already resolved; Angular renders before data arrives — every template needs a loading/empty/error state.
- Legacy pages often rely on full-page reloads to reset state; SPA components must reset explicitly (route param changes do NOT recreate components by default).
- `Html.DropDownListFor` with `SelectList` bakes selected-ness into markup; in Angular, selection is form state — port the *data source*, not the option tags.
