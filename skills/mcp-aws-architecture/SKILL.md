---
name: mcp-aws-architecture
description: Produce the AWS architecture for a governed MCP server — account layout, per-domain AgentCore Gateway, Policy, Identity, interceptor, private ingress (PrivateLink) and egress (VPC Lattice, Transit Gateway, Direct Connect), target type selection, quotas and a gateway-layer cost model — plus an editable draw.io diagram with official AWS icons exported to SVG. Use when asked for an MCP/AgentCore architecture, an AWS infra diagram, draw.io diagrams, or cost/quota sizing. Stage 5 of 7.
---

# AWS architecture (stage 5 · gate G4)

Read `references/aws-patterns.md` (this skill).

## Steps

1. **Pick the pattern** — A (machine agents, SigV4), B (user-delegated, JWT + 3LO), or C (private multi-partition, per-domain gateways; the enterprise default). Note: IAM inbound is rejected when any target uses 3LO.
2. **Choose target types per tool** from the table in the reference (Lambda for curated ERP verbs, OpenAPI/MCP server via VPC Lattice for private services, Runtime for stateful/long jobs). `validate_spec.py` rejects impossible combinations (e.g. Smithy or API Gateway targets reaching private systems).
3. **Size it** — `python3 <plugin>/scripts/cost_model.py mcp-spec.yaml --scale=1,5,25`. Check search rate (default 25/min), 200 TPS tool-call quota shared at account level, 100 targets/gateway, 6 MB payload. Present cost per *completed business task* when the user has token/compute assumptions.
4. **Diagram** —
   - `python3 <plugin>/scripts/gen_architecture.py mcp-spec.yaml -o docs/architecture.drawio`
   - `<plugin>/scripts/export_drawio.sh docs` → `docs/architecture.svg` (needs draw.io desktop; headless via `xvfb-run` on Linux; set `DRAWIO_BIN` if not on PATH).
   - For bespoke diagrams, write a short Python script using `scripts/drawio_kit.py` (`Diagram.group/aws/box/edge/legend`, `write_file`). Only icons listed in `AWS_ICONS` are verified to render; AgentCore has no dedicated icon — use `bedrock`.
   - Inspect the SVG (render it in a browser or Chromium headless screenshot) and fix overlaps before sharing. draw.io's own PNG export can clip labels; prefer SVG.
5. **Record Region gates** — AgentCore Policy coverage differs by Region; for EU workloads confirm Frankfurt (eu-central-1) or another Policy Region on the official page. Paris (eu-west-3) was reported Gateway-only.

## Output

`docs/architecture.drawio` + `.svg`, a cost table, and the G4 checklist (Region features, private connectivity both directions, quotas, cost envelope) appended to the ADR.
