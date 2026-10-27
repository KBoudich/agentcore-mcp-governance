# ADR: Governance and hosting for the `quality-certificates` MCP server

- **Status:** Proposed (2026-10-27)
- **Domain:** quality · **Business owner:** Head of Quality Systems · **Technical owner:** Quality digital product team · **Risk owner:** Group Quality Director
- **Highest tool tier:** T3

## Context

Let customer-service and quality agents retrieve inspection certificates and manage non-conformance reports without direct access to the business systems.

Hosting aws, primary Region eu-central-1, IdP entra-id, partition dimension legal_entity, isolation contractual, compliance gdpr, nis2, export-control.

## Decision

| Question | Outcome |
| --- | --- |
| Q1 MCP or not | MCP |
| Q2 Control plane | **AgentCore Gateway** — inbound auth CUSTOM_JWT |
| Q4 Partition model | Partitioned — dedicated domain gateway (and policy engine); export-controlled tools on a separate gateway |
| Q5 Server strategy | Wrap existing system APIs as Lambda/OpenAPI targets exposing curated business verbs |

### Option scores (weighted, 1–5)

| Option | Score |
| --- | ---: |
| AgentCore Gateway | 4.31 |
| Self-managed MCP gateway | 2.89 |
| App-managed endpoints (no MCP) | 2.83 |
| Direct MCP (no gateway) | 2.57 |

### Q3 Mandatory controls per tool

- **`get_inspection_certificate`** (T1, lambda target)
  - [ ] Schema review (no hidden writes)
  - [ ] Response caps and pagination
  - [ ] Default-deny Cedar permit per role
  - [ ] Partition-scope negative tests (Cedar AND backend)
  - [ ] Field minimisation
  - [ ] Invocation audit linked to caller
  - [ ] Bulk-extraction limit (rate + max_results)
- **`list_open_nonconformances`** (T1, lambda target)
  - [ ] Schema review (no hidden writes)
  - [ ] Response caps and pagination
  - [ ] Default-deny Cedar permit per role
  - [ ] Partition-scope negative tests (Cedar AND backend)
  - [ ] Field minimisation
  - [ ] Invocation audit linked to caller
  - [ ] Bulk-extraction limit (rate + max_results)
- **`create_nonconformance_draft`** (T2, lambda target)
  - [ ] Schema review (no hidden writes)
  - [ ] Response caps and pagination
  - [ ] Default-deny Cedar permit per role
  - [ ] Partition-scope negative tests (Cedar AND backend)
  - [ ] Field minimisation
  - [ ] Invocation audit linked to caller
  - [ ] Bulk-extraction limit (rate + max_results)
  - [ ] Idempotency key + duplicate-suppression test
  - [ ] State precondition checks
  - [ ] Proven compensation / undo
  - [ ] Before/after state in the business journal
- **`request_quality_hold_release`** (T3, lambda target)
  - [ ] Schema review (no hidden writes)
  - [ ] Response caps and pagination
  - [ ] Default-deny Cedar permit per role
  - [ ] Partition-scope negative tests (Cedar AND backend)
  - [ ] Field minimisation
  - [ ] Invocation audit linked to caller
  - [ ] Bulk-extraction limit (rate + max_results)
  - [ ] Idempotency key + duplicate-suppression test
  - [ ] State precondition checks
  - [ ] Proven compensation / undo
  - [ ] Before/after state in the business journal
  - [ ] Human approval bound to exact intent (who, what, amount, expiry)
  - [ ] Cedar argument limits + temporal policy
  - [ ] Reconciliation for unknown outcomes (no blind retry)
  - [ ] Pre-authored break-glass forbid, drill executed
  - [ ] Immutable evidence retention

## Rationale

- Q1: multiple agent consumers / shared platform justify a standard tool protocol.
- Q2: weighted score selects AgentCore Gateway (4.31 / 5).

## Responsibilities that stay with the application

Gateway provides reachability and enforcement (authN, Cedar, rate limits, sessions, token vault). Business authorization, partition data isolation, human approval, idempotency and transactional correctness remain the domain team's responsibility.

## Open verification gates (must close before this ADR is Accepted)

- [ ] Confirm Gateway + Policy availability in eu-central-1 on the official AgentCore Regions page.
- [ ] Verify how trusted partition context reaches each target type (header forwarding or interceptor) and that forged context is rejected.
- [ ] Confirm Policy behaviour on service errors (not just Cedar deny) before relying on default-deny alone.
- [ ] Confirm gateway execution-role granularity per target; prefer separate gateways per trust domain.
- [ ] Check the published AgentCore SLA and set SLOs; time a cross-Region IaC redeploy drill to measure RTO.
- [ ] Approval workflow, idempotency store and reconciliation job exist and pass the duplicate-write test.

## Reconsideration triggers

- A multi-cloud or portability mandate.
- A required Region without AgentCore Policy.
- A compliance finding against fail-open rate limiting.
- Gateway-layer cost becoming material relative to cost per completed business task.

