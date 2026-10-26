---
name: mcp-operations
description: Operate a governed MCP server in production — acceptance tests before go-live, runbooks (throttling, timeouts, revoked credentials, policy denial storms, catalogue drift, suspected cross-partition leakage, emergency tool shutdown), evidence reconstruction, cost and quota monitoring, DR drill. Use for go-live readiness, incident handling, or MCP/AgentCore operational reviews. Stage 7 of 7.
---

# Operate (stage 7 · gate G6)

Read `references/runbooks.md` and `references/acceptance-tests.md` (this skill).

## Before go-live (G6)

1. Run every acceptance test in `references/acceptance-tests.md` in stage; attach evidence to the ADR.
2. Rehearse: break-glass forbid for the highest-tier tool, revoked-consent flow, a timed-out write reconciled without duplication, and a cross-Region IaC redeploy (record the measured RTO).
3. Reconstruct one business transaction end to end from evidence: caller → partition → tool + schema version → policy decision → approval → business journal entry.
4. Dashboards and alarms: gateway errors/latency/throttles, policy denies by tool, interceptor denials, adapter rejections by reason, idempotency conflicts, approvals pending/expired, search rate vs quota, cost per business task.

## In production

- Incidents: follow `references/runbooks.md`; containment is targeted Cedar forbid + backend kill switch — never rate limits alone.
- Weekly: registry vs deployed catalogue drift; unused tools (no calls in 30 days → retire or justify); policy diffs reviewed.
- Quarterly: access review of policy/engine permissions, DR drill, re-verify AgentCore rates/quotas/Region coverage (`reference/agentcore-facts.json` carries the verification date).
- Any authority expansion (new write, widened bound) goes back to stage 2.
