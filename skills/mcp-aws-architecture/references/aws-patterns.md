# AWS patterns for governed MCP

## Account layout (enterprise default)

| Account | Owns |
| --- | --- |
| Network hub | Transit Gateway, Direct Connect (+ VPN backup), Route 53 Resolver, interface endpoints for Gateway ingress, egress inspection |
| MCP platform (dev / stage / prod) | one AgentCore Gateway + policy engine per business domain, AgentCore Identity providers, interceptor Lambdas, tool registry, KMS keys |
| Domain workload (per domain) | tool adapters, private MCP/OpenAPI services, idempotency + approval state, backend credentials |
| Security / log archive | org CloudTrail, CloudWatch cross-account observability, Object Lock evidence bucket, Security Hub, GuardDuty, Config |
| Delivery | pipelines (GitHub Actions OIDC or CodePipeline), Cedar tests, schema diffs |

## Patterns

- **A — machine identity:** agents on ECS/EKS/Lambda/Runtime call with SigV4 (`bedrock-agentcore:InvokeGateway`). Simplest; no user delegation.
- **B — user-delegated:** remote MCP clients bring a JWT from the corporate IdP (CUSTOM_JWT); AgentCore Identity brokers 3LO tokens for SaaS. Required when any target uses 3LO.
- **C — private multi-partition (recommended):** per-domain gateways, JWT with partition claim, Cedar ENFORCE, interceptor-injected trusted context, private egress to domain accounts, backend row-level scope.

## Target type selection

| Target | Use for | Private reach | Notes |
| --- | --- | --- | --- |
| Lambda | curated business verbs over ERP/legacy | VPC-attached function | you author the schema; cheapest path |
| OpenAPI | existing REST services | `privateEndpoint` via VPC Lattice | one domain per config |
| MCP server | existing/stateful MCP servers, vendor MCP | VPC Lattice | 3LO, elicitation, sampling, streaming; govern prompts/resources separately |
| Runtime | long-running/stateful tools (8 h async) | AWS backbone | verify policy applicability on the route |
| HTTP passthrough | any HTTP endpoint, inference | yes | provide a schema to enable policy features |
| API Gateway | regional REST only | **no private APIs** | export as OpenAPI instead; no OAuth/cross-account |
| Smithy | Smithy-modelled AWS APIs | **no privateEndpoint** | Support case for private connectivity |

## Ingress vs egress

Test them separately: caller → Gateway (PrivateLink interface endpoint, endpoint policy, DNS) and Gateway → target (Lattice / VPC Lambda, security groups, private CA trust anchors, TLS). Confirm the public route is denied for your configuration rather than assuming it.

## Quotas that shape the design (defaults, Oct 2026)

100 targets/gateway · 1,000 tools/target · 200 TPS tool calls (gateway **and** account) · 5,000 concurrent connections · 25 search calls/min · 6 MB payload · 15 min invocation timeout · 5 TPS control plane (batch IaC) · sessions 1 h default / 8 h max.

## Cost (gateway layer only)

$5/M invocations · $25/M search · $25/M policy authorizations · $0.02 per 100 tools/month · $0.006/GB customer-VPC egress · Identity free through Gateway. Add target compute, interceptor invocations, CloudWatch, IdP, networking and inference to get cost per completed business task.

## DR

No cross-Region replication of gateways, policies, credential providers or consent is documented. Plan IaC redeploy in the DR Region, client endpoint redistribution (gateway URLs embed generated IDs; a CNAME does not fix TLS/SigV4 hostnames), 3LO re-consent, and time the drill to state a real RTO.
