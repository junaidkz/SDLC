---
name: wcf-to-rest-mapping
description: Rules for translating WCF service contracts to REST/Web API endpoints, DTOs, and TypeScript interfaces. Use whenever reading [ServiceContract]/[OperationContract]/[DataContract] code, Reference.cs proxies, web.config bindings, or designing the endpoints and TS models the Angular app will consume.
---

# WCF → REST/Web API Mapping

## Operations → endpoints
| WCF pattern | REST |
|---|---|
| `GetCustomer(int id)` | `GET /api/customers/{id}` |
| `GetCustomers(criteria)` | `GET /api/customers?field=value&page=…` (POST /search only if criteria are genuinely complex) |
| `SaveCustomer(dto)` upsert | Split: `POST /api/customers` (create) + `PUT /api/customers/{id}` (update). Upsert semantics must not leak to the SPA |
| `DeleteCustomer(id)` | `DELETE /api/customers/{id}` |
| Verb-y ops (`ApproveOrder`) | `POST /api/orders/{id}/approve` — action sub-resource, don't force fake CRUD |
| Chatty sequences one page calls together | One composed `GET /api/pages/{page}/payload` endpoint (BFF style) — the SPA should make 1–2 calls per page, not replay WCF chattiness |
| Ops with `out`/`ref` params | Response DTO with named properties |
| `MessageContract`/streaming | `FileStreamResult` / multipart upload endpoints |

## DataContract → DTO → TypeScript
- Strip WCF artifacts: `ExtensionDataObject`, `<Field>Specified` boolean pairs (fold into nullable properties), `ArrayOfX` wrappers (plain arrays).
- Wire format: camelCase JSON; dates as ISO 8601 strings (`string` in TS, convert at the service edge; kill any legacy `/Date(ticks)/` at the API boundary, never in Angular).
- `[DataMember(IsRequired=…)]`/nullability → TS `| null` and `?` deliberately; the TS interface is the contract, keep it exact.
- Enums serialized as strings (`JsonStringEnumConverter`) → TS string-literal unions, not numeric enums.
- `decimal` money → `number` is usually fine for display; flag any client-side arithmetic on money as a risk.

## Faults → problem+json
- `FaultContract<TDetail>` → RFC 7807 `application/problem+json`; `TDetail` fields go into extension members.
- Validation faults → 400 with an `errors: { field: string[] }` map (mirrors ModelState shape) so Angular can hydrate `FormControl.setErrors`.
- Business-rule faults → 409/422 with a stable machine-readable `code` the SPA can branch on. Never branch on human-readable messages.
- One Angular error interceptor normalizes all of this into a single `ApiError` type.

## Behaviors & config to account for
- `web.config` binding quirks: timeouts (`sendTimeout`), `maxReceivedMessageSize` → API request limits + HttpClient timeout strategy for known long-running ops.
- WCF sessions/`InstanceContextMode` state → REST is stateless; any per-session server state must move to the DB, a cache keyed by user, or the client. Flag every occurrence as a decision.
- Transport security / Windows auth on bindings → the SPA auth design (JWT/cookie); don't silently drop `[PrincipalPermission]`-style checks — they become authorization policies.
- `IsOneWay=true` fire-and-forget ops → `202 Accepted` (+ status endpoint if the caller ever polls).

## Traceability
Every produced endpoint spec and TS interface must state which WCF operation/DataContract it replaces. The migration is done when every `[OperationContract]` in the inventory maps to an endpoint or a documented "retired" decision.
