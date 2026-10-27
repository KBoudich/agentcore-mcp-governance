# MCP governance decision framework

Five questions, asked in order, per MCP server. Knock-outs first, weighted choices second. `scripts/decide.py` implements this file; keep both in sync.

## Q1 — Should this be MCP at all?

Choose MCP when at least one holds:

- two or more agent consumers (or agent frameworks) need the same tools;
- tools must be discoverable (catalogue, semantic search) rather than hard-wired;
- users must delegate access to many tools/SaaS systems through one endpoint;
- the server joins a shared platform that already governs other MCP servers.

Otherwise keep an ordinary API and a framework tool adapter. MCP adds protocol surface (prompts, resources, sessions, elicitation) that must also be governed.

## Q2 — Which control plane?

### Knock-outs

| Condition | Outcome |
| --- | --- |
| Portability / multi-cloud mandate, or hosting not on AWS | Self-managed MCP gateway (e.g. on EKS) or a portability layer; AgentCore cannot be the sole plane |
| Primary Region lacks AgentCore Policy and any tool is ≥ T1 | Move to a Region with Policy (for EU: eu-central-1 reported) or defer T1+ tools |
| ≤ 2 servers, one team, only T0 tools, no user delegation | Direct MCP, no gateway |

### Weighted comparison (default weights)

| Criterion | Weight | AgentCore Gateway | Self-managed gateway | Direct MCP | App endpoints |
| --- | ---: | :---: | :---: | :---: | :---: |
| Central, testable authorization (Cedar, discovery filtering) | 0.22 | 5 | 3 | 1 | 2 |
| Operational burden (lower is better → higher score) | 0.18 | 4 | 2 | 3 | 3 |
| Time to value | 0.14 | 4 | 2 | 5 | 4 |
| User delegation / token vault (3LO) | 0.12 | 5 | 2 | 1 | 2 |
| Catalogue scale (search, many targets) | 0.12 | 5 | 4 | 1 | 1 |
| Cost at scale | 0.12 | 4 | 3 | 5 | 5 |
| Portability | 0.10 | 2 | 5 | 4 | 4 |

Adjustments: +0.15 portability when mandated; +0.08 delegation when 3LO is needed; +0.08 central authorization when any tool is T2/T3. Weights are renormalised.

Why AgentCore usually wins on AWS: managed inbound/outbound auth, default-deny Cedar with discovery filtering, a token vault that is free through the gateway, sessions, semantic search, rate limits — at a gateway-layer cost that stays negligible until millions of calls (policy checks at $25/M are the largest meter, not invocations at $5/M).

## Q3 — Which controls does each tool need?

Classify by **worst credible effect**, including bulk extraction and downstream automation.

| Tier | Examples | Mandatory controls (cumulative) | Review |
| --- | --- | --- | --- |
| T0 | public reference lookup | schema review, response caps, default-deny permit per role | standard |
| T1 | orders, certificates, PII | partition negative tests in Cedar **and** backend, field minimisation, audit link, bulk-extraction limit | security |
| T2 | draft NCR, draft PO | idempotency key + duplicate test, state preconditions, proven compensation, before/after journal | business owner + security |
| T3 | release quality hold, approve PO, post payment | approval bound to exact intent, Cedar argument limits (+ temporal), reconciliation for unknown outcomes, rehearsed break-glass forbid, immutable evidence | business + security + compliance; risk owner signs |

## Q4 — Partition model

| Model | When | Mechanics |
| --- | --- | --- |
| Pooled | default; logical isolation acceptable | one domain gateway; partition = JWT claim; Cedar condition + backend row-level scope |
| Partitioned | contractual isolation, export-controlled or regulated data | separate gateway + policy engine for that data class; tighter blast radius |
| Siloed | regulatory / JV / customer contract requires it | dedicated account + gateway per partition; 1,000-gateway and 5 TPS control-plane limits apply |

Never: partition from a tool argument, from a session id, or from a rate-limit bucket.

## Q5 — Build, wrap or reuse the server

1. **Reuse** a vendor MCP server only behind the gateway, with a tool allow-list, prompt/resource inventory and capability-drift detection (unknown tools quarantined).
2. **Wrap** existing APIs as Lambda or OpenAPI targets exposing curated business verbs — the default for any system of record that already has an API (ERP, LIMS, MES, PLM, CRM, ITSM, SaaS).
3. **Build** a custom MCP server on AgentCore Runtime only for stateful sessions, elicitation/sampling, or long-running jobs.

## Output and reconsideration

One ADR per server: control plane + Region, inbound auth, tiers and controls per tool, partition model, server strategy, named owners, open gates, cost envelope. Reconsider when a portability mandate appears, a required Region lacks Policy, a compliance finding hits the fail-open rate limiter, or gateway cost becomes material relative to cost per completed business task.
