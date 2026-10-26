# MCP threat model (AgentCore Gateway)

| # | Threat | Preventive control | Enforcement point | Residual risk / test |
| --- | --- | --- | --- | --- |
| 1 | Unauthenticated caller | CUSTOM_JWT (issuer, audience, client) or SigV4; never `NONE` outside dev | Gateway inbound authorizer | stolen tokens → short lifetimes, conditional access |
| 2 | Public route bypassing private ingress | PrivateLink interface endpoint + test that the public path is denied for your configuration | network, endpoint policy | test both paths explicitly |
| 3 | Over-broad tool access | default deny; one permit per tool and scope; discovery filtered | Cedar | mis-authored permit → negative tests |
| 4 | Argument abuse (amount, plant, quantity) | `context.input.*` conditions; adapter re-validates | Cedar + adapter | Cedar sees args, not record ownership |
| 5 | Cross-partition data access | partition from validated claim → interceptor → backend row-level scope | backend (authoritative) | **Gateway identity alone is insufficient** |
| 6 | Forged identity in arguments | interceptor strips identity fields, injects `_trusted_context`; backend ignores args | interceptor + backend | test forged rows in the matrix |
| 7 | Backend reachable around the gateway | Lambda invocable only by gateway role; private services accept only gateway-originated calls | IAM, SG, Lattice auth | direct-call test from an agent role must fail |
| 8 | Confused deputy (gateway role used for any user) | per-trust-domain gateways; role scoped to its functions; partition carried separately from service credential | IAM + adapter | review role-to-target granularity |
| 9 | Prompt injection via tool output | least-privilege tools, T3 approval, output minimisation, Guardrails via Policy where available | agent + gateway + approvals | legitimate tools can still carry instructions |
| 10 | Unprotected MCP prompts/resources | Policy evaluates tools only; disable or protect prompts/resources at the target | target | inventory every exposed method |
| 11 | Duplicate consequential write on retry | idempotency key + intent hash; reconciliation on unknown outcome | adapter + state store | timeout ≠ not executed |
| 12 | Approval bypass / replay | approval bound to intent hash, approver entitlement, expiry, single use | approval service | re-check at execution time |
| 13 | Runaway consumption | rate limits on partition/user dimensions; session budgets (temporal policies) | gateway | **fails open on transient errors** — not a security control |
| 14 | Credential theft (SaaS tokens) | AgentCore Identity vault (KMS); agents never see refresh tokens | Identity | provider-side revocation → re-consent flow |
| 15 | Catalogue drift (vendor MCP adds tools) | registry vs deployed diff; unknown tools quarantined (no permit) | CI + drift job | alert on new tool names |
| 16 | Policy weakened silently | engine mode and detach permissions restricted; policy diffs need second approver | IAM + CI | audit CloudTrail for policy API calls |
| 17 | Evidence gaps | correlate caller → partition → tool version → decision → business transaction; Object Lock retention | observability + journal | test reconstruction of one transaction |
