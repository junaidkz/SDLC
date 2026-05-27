# OWASP Top 10 (2026) — Reference for the review-owasp Skill

Loaded only when the Reviewer needs to look up the specifics of a category while writing a finding. Not in the hot context.

This file is structured for **lookup**, not reading start-to-finish. Each section is self-contained.

---

## A01 — Broken Access Control

**What it is**: User can perform actions or read data outside intended permissions.

**Spotting patterns**:
- New route handler without `[Authorize]` / equivalent guard.
- Object access by ID in URL/body without verifying caller owns the object (classic IDOR).
- Tenant context dropped between layers (`tenantId = null` paths).

**Reviewer phrasing**:
> `[SEVERITY: blocking] [SEC-A01] new route POST /orders/{id}/cancel has no ownership check`
> Where: `src/Orders/OrdersController.cs:84`
> Why: any authenticated user can cancel any order by ID.
> Suggested fix: verify `order.UserId == User.Id()` before mutation.

---

## A02 — Cryptographic Failures

**Spotting patterns**:
- Secrets in code (`apiKey = "sk-..."`), connection strings with passwords.
- Weak hashing (`MD5`, `SHA1`) for passwords or sensitive data.
- TLS verification disabled (`ServerCertificateCustomValidationCallback = (a,b,c,d) => true`).
- Predictable IDs (sequential ints) for resources that should be unguessable.

---

## A03 — Injection

**SQL**: any string concatenation into a query — REJECT.
- C#: `new SqlCommand($"SELECT * FROM Users WHERE Id={id}")` → use parameters.
- EF Core: `FromSqlRaw($"... {id}")` → `FromSqlInterpolated` or parameterised.
- Dapper: `Execute($"... {id}")` → `Execute("... @id", new { id })`.

**Command**: `Process.Start`, `child_process.exec` with user-derived args — REJECT.

**LDAP/XPath/Template**: same principle.

---

## A04 — Insecure Design

**Spotting patterns**:
- Missing rate limiting on auth/login endpoints.
- No abuse pathway considered (the diff adds a feature without a "what if attacker uses this" comment).
- Trust boundaries unclear (admin actions reachable from non-admin contexts).

**This category needs judgment more than pattern matching.** Quote the Planner's risk section back to the user if it didn't address abuse paths.

---

## A05 — Security Misconfiguration

**Spotting patterns**:
- Default credentials, debug pages enabled in prod config.
- Verbose error pages returning stack traces.
- CORS `AllowAnyOrigin()` + `AllowCredentials()` together (browsers reject; bug).
- Missing security headers (`X-Content-Type-Options`, `Strict-Transport-Security`).

---

## A06 — Vulnerable & Outdated Components

**Spotting patterns**:
- New direct dependency added without an ADR → REJECT (project rule).
- `audit` task output showing `high` or `critical` — REJECT until upgraded.
- Pinned-to-old-version overrides — flag.

---

## A07 — Identification & Authentication Failures

**Spotting patterns**:
- Weak session cookies (missing `HttpOnly` / `Secure` / `SameSite`).
- Long-lived tokens without rotation (see `REQ-AUTH-014` pattern).
- No lockout / throttle on credential endpoints.
- Logging credentials or tokens, even at debug level.

---

## A08 — Software & Data Integrity Failures

**Spotting patterns**:
- `BinaryFormatter`, `JavaScriptSerializer`, `pickle.loads`, `yaml.load` (without `SafeLoader`).
- `JsonSerializer.Deserialize<T>(... TypeNameHandling.All)`.
- Untrusted gRPC/protobuf input with `Any`-typed payloads.
- Auto-update mechanisms without signature verification.

---

## A09 — Security Logging & Monitoring Failures

**Spotting patterns**:
- Auth success/failure not logged.
- Authz denials not logged (an attacker probing should leave traces).
- Sensitive events without structured context (no user id, no source IP, no request id).

**Note**: don't over-correct — logging tokens or PII is **worse** than not logging. Find the middle.

---

## A10 — Server-Side Request Forgery (SSRF)

**Spotting patterns**:
- `HttpClient.GetAsync(userProvidedUrl)` without scheme/host validation.
- URL fetchers reachable by untrusted users.
- Webhooks accepting destinations from request body.
- Cloud metadata endpoints (`169.254.169.254`) reachable.

---

## Project-specific extensions

These are not OWASP but apply to **this repo** and have the same severity. The `review-owasp` skill walks them after the OWASP list.

### Dynamic invocation from untrusted strings — blocking
`eval`, `new Function()`, `setTimeout(string)`, `Invoke-Expression`, `Activator.CreateInstance(typeName)` where the type/code is derived from untrusted input. Always REJECT unless an ADR justifies and the input is gated.

### Hard-coded outbound URLs — major
New `HttpClient.GetAsync("https://...")` with the URL inline. Move to config + allowlist. The allowlist is enforced at startup.

### Missing audit on touched paths — blocking
If the diff touches a file but no `emit-audit` event references that file, the Implementer either skipped the skill or has a bug. Either way the audit trail is incomplete — REJECT.

### Untagged work — blocking
New public symbols, tests, or commits missing `@req` / `@jira` / `[REQ-ID]` per `stamp-traceability`. REJECT — the RTM won't build.

---

## How to phrase findings

Compact, machine-parseable, fix-actionable. Bad and good examples:

❌ "The code seems insecure because the variable is passed unsafely."
✅ "`userId` is interpolated into SQL at line 84; use a parameterised query."

❌ "Consider adding logging here."
✅ "Auth failure at line 30 not logged — add `_logger.LogWarning(...)` with `req_id`, `userId`, `sourceIp`."
