# Acceptance tests (beyond the happy path)

| # | Test | Pass condition |
| --- | --- | --- |
| 1 | Allowed vs denied principal call `tools/list` | lists differ; denied sees no unauthorised tool |
| 2 | Listed tool called with out-of-bounds arguments | denied by Cedar argument condition |
| 3 | Valid caller requests a record of another partition | Cedar allows (it cannot know ownership) **and** backend rejects |
| 4 | Missing partition claim | denied at Cedar and by interceptor |
| 5 | Forged `entity_id` / `_trusted_context` in arguments | overwritten by interceptor; backend uses trusted value |
| 6 | Agent role invokes the adapter Lambda / private service directly | access denied (only gateway role) |
| 7 | Public route to the gateway from outside the private path | denied (or documented acceptance) |
| 8 | Same write twice with the same idempotency key | one effect; identical response |
| 9 | Same key, different arguments | rejected |
| 10 | Write times out, client retries | no duplicate; reconciliation resolves the unknown outcome |
| 11 | T3 call without approval | only a PENDING approval exists; nothing executed |
| 12 | Approval replayed / expired / approver lacks entitlement | execution refused |
| 13 | Revoked user consent (3LO) | outbound call fails; re-consent triggered |
| 14 | Cross-user session reuse (`Mcp-Session-Id` of another user) | rejected (sessions are user-scoped) |
| 15 | Break-glass forbid deployed | tool hidden and denied within the measured propagation time |
| 16 | Policy engine in LOG_ONLY in stage | would-deny decisions visible in traces; none in prod engine |
| 17 | Load test at 2× expected peak | billed invocations reconcile with expected traffic (no hidden discovery/retry multiplier) |
| 18 | Evidence reconstruction | one transaction traceable caller → partition → tool version → decision → approval → business record |
| 19 | DR redeploy in second Region | measured RTO recorded; clients reconfigured; consent re-established |
