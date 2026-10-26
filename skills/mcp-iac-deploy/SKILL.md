---
name: mcp-iac-deploy
description: Scaffold and deploy a governed MCP server on AWS with CDK (aws-cdk-lib AgentCore L1 constructs) — Gateway with CUSTOM_JWT, policy engine and Cedar policies, REQUEST interceptor, Lambda adapter with idempotency and approvals, KMS, DynamoDB, and a GitHub Actions pipeline promoting dev → stage (LOG_ONLY) → prod (ENFORCE) with smoke tests and a break-glass path. Use when building, deploying or writing IaC/CI for an MCP server or AgentCore Gateway. Stage 6 of 7.
---

# Build & deploy (stage 6 · gate G5)

## Steps

1. **Scaffold** from the spec:
   `python3 <plugin>/scripts/scaffold_deploy.py mcp-spec.yaml -o infra/`
   This copies `templates/cdk/` (this skill) and generates `config/tools.json`, `config/mcp.json`, `policies/*.cedar`, `policies/breakglass/`, `lambda/adapter/tool_registry.py`, `tests/decision-matrix.md`. Only `lambda` targets are scaffolded; add other target types to the stack by hand.
2. **Configure** `infra/config/mcp.json`: IdP `discoveryUrl`, `allowedAudience`, cost-centre tags. For Entra ID use the v2.0 OIDC discovery URL of the tenant and an app registration exposing the scopes `<domain>/read|write|propose`.
3. **Implement the adapter** — replace `backend_*` stubs in `lambda/adapter/handler.py`. Keep the invariants: identity only from `_trusted_context`; partition filter inside the backend query; writes through `_idempotent`; T3 tools only create approvals. Pass `-c vpcId=vpc-…` to attach the adapter to a VPC that reaches on-prem via TGW/DX.
4. **Build checks** — `npm ci && pip install -r lambda/interceptor/requirements.txt -t lambda/interceptor/ && npx tsc --noEmit && npx cdk synth -c stage=dev`.
5. **Pipeline** — copy `infra/.github/workflows/mcp-deploy.yml` to the repo's `.github/workflows/`, vendor the plugin under `tools/mcp-architect/` (`python3 <plugin>/scripts/install.py .` does this), create GitHub environments `dev`, `stage`, `prod` (required reviewers on prod) with `AWS_DEPLOY_ROLE_ARN`, `AWS_REGION`, optional `SHADOW_POLICIES`, and secrets `SMOKE_TOKEN_ALLOWED` / `SMOKE_TOKEN_DENIED` from test identities.
6. **Promote**
   - dev, stage: engine `LOG_ONLY` (override `-c engineMode=ENFORCE` to rehearse); review would-deny decisions in CloudWatch traces.
   - prod: engine always `ENFORCE`; new/changed policies shadowed with `-c shadowPolicies=a,b` then flipped to `ACTIVE`.
   - smoke test after each deploy: initialize → `tools/list` filtered per principal → denied `tools/call` rejected.
7. **Break-glass** — `workflow_dispatch` with `breakglass_tool=<name>` copies the pre-authored forbid into the deployed set (prod approval still required). Rehearse it before go-live (gate G6).

## What the template verified

Props and attributes were checked against `aws-cdk-lib` 2.274.0 (`CfnGateway`, `CfnGatewayTarget`, `CfnPolicyEngine`, `CfnPolicy`) and the example synthesises. Still verify before production: IAM actions for policy evaluation on the gateway role, interceptor header behaviour for your IdP, `exceptionLevel` handling, and whether injected `_trusted_context` must be declared in the tool schema for your target type.
