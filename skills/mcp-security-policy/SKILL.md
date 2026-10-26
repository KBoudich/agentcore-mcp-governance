---
name: mcp-security-policy
description: Threat-model an MCP server and author its AgentCore Cedar policies with a positive/negative decision test matrix — default deny, scope and partition claim conditions, argument limits, break-glass forbids, LOG_ONLY shadowing, trusted-context interceptor, confused-deputy and prompt-injection controls. Use when writing Cedar for AgentCore Gateway, reviewing MCP security, or planning LOG_ONLY to ENFORCE. Stage 4 of 7.
---

# Security & policy (stage 4 · gate G3)

Read `references/threat-model.md` and `references/cedar-patterns.md` (this skill).

## Steps

1. **Threat model** — walk the table in `references/threat-model.md` for this server. For each threat record the preventive control, the enforcement point (IdP, Gateway authorizer, Cedar, interceptor, backend) and the residual risk. Anything enforced only "by the model" is not a control.
2. **Trusted context** — decide how identity and partition reach the backend for each target type. Default: REQUEST interceptor verifies the token and injects `_trusted_context`; the backend accepts identity only from there and is reachable only from the gateway role. Verify per target type; header forwarding behaviour differs.
3. **Generate policies** — `python3 <plugin>/scripts/scaffold_deploy.py mcp-spec.yaml -o infra/` writes one default-deny `permit` per tool (`infra/policies/*.cedar`), a break-glass `forbid` per tool (`infra/policies/breakglass/`, not deployed), and `infra/tests/decision-matrix.md`.
4. **Harden by hand** — add argument conditions (`context.input.*`) for business limits, replace TODOs on T2/T3, add temporal policies (≤ 20 per engine) for session budgets where needed. Check every identifier against the Cedar schema AgentCore generates from the deployed tools.
5. **Review IdP claims** — Entra ID delegated scopes arrive in `scp` (space-delimited); avoid scope names that are prefixes of each other because policies use `like "*scope*"`. Confirm how multi-valued claims map to principal tags before relying on them.
6. **Rollout** — dev/stage engine in `LOG_ONLY`; prod engine always `ENFORCE`; a new or changed policy ships in prod with `enforcementMode: LOG_ONLY` (`-c shadowPolicies=<name>`) until its decisions are reviewed, then `ACTIVE`.
7. **Run the decision matrix** in stage for both discovery (`tools/list`) and invocation (`tools/call`), and the backend column. Gate G3 closes only when every row passes, including forged-context rows.

## Separation of duties

Tool authors propose policies; a policy approver (security) reviews; an automation identity releases. Nobody can both change a policy and approve its promotion. Permissions that detach the policy engine or switch the engine mode are break-glass only.
