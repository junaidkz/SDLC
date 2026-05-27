---
name: review-owasp
description: Use when reviewing a code diff for security issues. Walks the diff against OWASP Top 10 + the repo's no-eval / no-hardcoded-URL / no-secret rules + input-validation requirements. Primarily used by the Reviewer agent; also runnable on demand on any branch via `/review-owasp`.
user-invokable: true
disable-model-invocation: false
allowed-tools: ['search', 'usages', 'changes', 'problems']
---

# Review a diff for security issues

Walk the diff with this checklist. Findings are formatted per the Reviewer's output spec (`STATUS: REJECTED` + `FINDINGS` block).

## When to use
- The Reviewer is walking a diff submitted by the Implementer.
- A user invoked `/review-owasp` on a branch outside the normal flow (e.g. auditing legacy code).

## When NOT to use
- The diff is documentation-only — no security surface to review.
- The diff is purely generated output (lock files, auto-formatted code).
- The user wants a code review for style / architecture — different skill.

## Severity rule

Anything in this skill that fails is **at least `major`**. Anything tagged "blocking" below is `blocking`. There is no `minor` in security.

## Checklist (walk the diff once per item)

### 1. Injection — blocking

- SQL/NoSQL: every query parameterised? Look for string concatenation into `SqlCommand`, `Dapper.Execute`, raw `mongoose.find({ $where: ... })`.
- Command: any `Process.Start`, `child_process.exec`, `os.system`, `subprocess.run(..., shell=True)` with user-derived input?
- LDAP / XPath / template: same principle — never interpolate user input into a query string.

### 2. Authentication & session — blocking

- New routes/endpoints: protected by the same auth attribute/guard as their neighbours?
- New cookie writes: `HttpOnly`, `Secure`, `SameSite` set explicitly?
- New token issuance: short-lived? Refresh-token rotation in play (REQ-AUTH-014)?

### 3. Sensitive data exposure — blocking

- Secrets in code, configs, logs, error messages, or commit content?
- Logging that could include PII or tokens? (`_logger.LogInformation("user logged in: {User}", user)` where `user` includes email is borderline — depends on log destination.)
- Stack traces returned to the client?

### 4. XXE / SSRF — blocking

- Any new `XmlDocument`, `XmlReader`, `XDocument`: DTD/external-entity processing disabled?
- Any new outbound HTTP/HTTPS call: destination from a config allowlist, not user input?
- URL fetchers: validate scheme + host before fetching.

### 5. Access control — blocking

- New routes check the right role/permission?
- Object references (IDs in URLs) verify the caller owns the object (no IDOR)?
- Multi-tenant: tenant context applied to every query?

### 6. Insecure deserialization — blocking

- `BinaryFormatter`, `JavaScriptSerializer`, `pickle.loads`, `yaml.load` (without `SafeLoader`), `Marshal.load`? REJECT unless from a trusted source AND signature-verified.
- `JsonSerializer.Deserialize<T>` with `TypeNameHandling.All`? REJECT.

### 7. Vulnerable components — blocking

- Any new dependency added? Check `docs/adr/`. If no ADR exists for it, REJECT.
- Run the audit task (`runTasks` → `audit`); fail on `high`/`critical` advisories.

### 8. Insufficient logging — major

- Auth success/failure logged?
- Authz denials logged?
- New audit-worthy events (token rotation, role changes) emitting structured logs?

### 9. Dynamic invocation from untrusted strings — blocking

- `eval`, `new Function()`, `setTimeout(string)`, `Invoke-Expression`, `Activator.CreateInstance(typeName)`, dynamic LINQ from user input — REJECT on sight unless an ADR justifies and constrains it.

### 10. Hard-coded outbound URLs — major

- New `HttpClient.GetAsync("https://...")` with the URL inline? REJECT — move to config + allowlist.

## Repo-specific rules (on top of OWASP)

- **No package installs without an ADR.** Use the `propose-adr` skill flow.
- **Audit emissions** for the touched code path — confirm `emit-audit` events were emitted for the Implementer's edit steps.
- **REQ-ID + Jira stamps** on every new symbol — see the `stamp-traceability` skill.

## Output

Use the Reviewer's `STATUS: REJECTED` format. Each finding:

```
[SEVERITY: blocking|major] [SEC-<n>] <one-line summary>
Where: <file:line>
Why: <one paragraph>
Suggested fix: <one line>
```

If everything passes, include a `Security checks: passed` line in the `APPROVED` output enumerating the checklist items walked.

## Reference material (load only when needed)

- `references/owasp-top10-2026.md` — full details per category with spotting patterns and example finding phrasings. The Reviewer reads this *only* when writing a finding for a specific category, not on every review.
