#!/usr/bin/env python3
"""Apply the MCP governance decision framework to a spec and emit an ADR (Markdown).

    decide.py mcp-spec.yaml [--json]

Q1 Should this be MCP at all?            (knock-out)
Q2 Which control plane?                  (knock-outs, then weighted scoring)
Q3 Which controls does each tool need?   (risk tier -> mandatory controls)
Q4 Which partition model?                (pooled / partitioned / siloed)
Q5 Build, wrap or reuse the server?

Weights and thresholds are starting points; the Design Authority owns them.
"""

from __future__ import annotations

import datetime as dt
import json
import sys

from spec_io import load_reference, load_spec

CONTROLS = {
    "T0": ["Schema review (no hidden writes)", "Response caps and pagination", "Default-deny Cedar permit per role"],
    "T1": ["Partition-scope negative tests (Cedar AND backend)", "Field minimisation", "Invocation audit linked to caller",
           "Bulk-extraction limit (rate + max_results)"],
    "T2": ["Idempotency key + duplicate-suppression test", "State precondition checks", "Proven compensation / undo",
           "Before/after state in the business journal"],
    "T3": ["Human approval bound to exact intent (who, what, amount, expiry)", "Cedar argument limits + temporal policy",
           "Reconciliation for unknown outcomes (no blind retry)", "Pre-authored break-glass forbid, drill executed",
           "Immutable evidence retention"],
}
TIERS = ["T0", "T1", "T2", "T3"]

# Criteria weights (sum = 1.0) and option scores 1-5.
CRITERIA = {
    "central_authorization": 0.22,
    "user_delegation": 0.12,
    "operational_burden": 0.18,
    "portability": 0.10,
    "time_to_value": 0.14,
    "catalog_scale": 0.12,
    "cost_at_scale": 0.12,
}
OPTIONS = {
    "AgentCore Gateway": {"central_authorization": 5, "user_delegation": 5, "operational_burden": 4, "portability": 2,
                          "time_to_value": 4, "catalog_scale": 5, "cost_at_scale": 4},
    "Self-managed MCP gateway": {"central_authorization": 3, "user_delegation": 2, "operational_burden": 2,
                                 "portability": 5, "time_to_value": 2, "catalog_scale": 4, "cost_at_scale": 3},
    "Direct MCP (no gateway)": {"central_authorization": 1, "user_delegation": 1, "operational_burden": 3,
                                "portability": 4, "time_to_value": 5, "catalog_scale": 1, "cost_at_scale": 5},
    "App-managed endpoints (no MCP)": {"central_authorization": 2, "user_delegation": 2, "operational_burden": 3,
                                       "portability": 4, "time_to_value": 4, "catalog_scale": 1, "cost_at_scale": 5},
}


def adjust_weights(spec: dict) -> dict:
    ctx = spec.get("context") or {}
    w = dict(CRITERIA)
    if ctx.get("portability_required"):
        w["portability"] += 0.15
    if ctx.get("user_delegation_to_saas"):
        w["user_delegation"] += 0.08
    if max_tier(spec) in ("T2", "T3"):
        w["central_authorization"] += 0.08
    total = sum(w.values())
    return {k: v / total for k, v in w.items()}


def max_tier(spec: dict) -> str:
    tiers = [t.get("tier", "T0") for t in spec.get("tools") or [] if t.get("tier") in TIERS]
    return max(tiers, key=TIERS.index) if tiers else "T0"


def decide(spec: dict) -> dict:
    facts = load_reference("agentcore-facts.json")
    ctx = spec.get("context") or {}
    tools = spec.get("tools") or []
    consumers = spec.get("consumers") or []
    region = ctx.get("primary_region", "")
    top = max_tier(spec)
    gates: list[str] = []
    rationale: list[str] = []

    # Q1
    agent_consumers = [c for c in consumers if c.get("kind") in ("agent", "human-client")]
    q1_mcp = len(agent_consumers) >= 2 or ctx.get("user_delegation_to_saas") or len(tools) >= 5 \
        or ctx.get("other_mcp_servers_on_platform", 0) > 0
    q1 = "MCP" if q1_mcp else "Not MCP — normal API + framework tool adapter"
    rationale.append(
        "Q1: " + ("multiple agent consumers / shared platform justify a standard tool protocol."
                  if q1_mcp else "single consumer and small surface: MCP adds protocol and governance overhead.")
    )

    # Q2 knock-outs
    knockout = None
    if not q1_mcp:
        knockout = "App-managed endpoints (no MCP)"
    elif ctx.get("hosting") != "aws" or ctx.get("portability_required"):
        knockout = "Self-managed MCP gateway"
        rationale.append("Q2: portability / non-AWS hosting knocks out a single-cloud managed gateway as the sole plane.")
    elif region in facts["regions"]["gateway_without_policy_reported"] and top != "T0":
        gates.append(f"Region {region} is reported without AgentCore Policy: move to a Policy Region or defer T1+ tools.")
    elif (ctx.get("other_mcp_servers_on_platform", 0) <= 1 and top == "T0"
          and not ctx.get("user_delegation_to_saas") and len(agent_consumers) <= 1):
        knockout = "Direct MCP (no gateway)"
        rationale.append("Q2: one small T0 server, one team, no delegation — a gateway adds cost and latency for little benefit.")

    weights = adjust_weights(spec)
    scores = {name: round(sum(weights[c] * s[c] for c in weights), 2) for name, s in OPTIONS.items()}
    plane = knockout or max(scores, key=scores.get)
    if not knockout:
        rationale.append(f"Q2: weighted score selects {plane} ({scores[plane]} / 5).")

    # Q3
    per_tool = []
    for t in tools:
        tier = t.get("tier", "T0")
        controls = []
        for lvl in TIERS[: TIERS.index(tier) + 1]:
            controls.extend(CONTROLS[lvl])
        per_tool.append({"name": t.get("name"), "tier": tier, "target": t.get("target_type"), "controls": controls})

    # Q4
    iso = ctx.get("isolation_requirement", "logical")
    classes = {c for t in tools for c in t.get("data_classes") or []}
    if iso == "regulatory":
        partition = "Siloed — dedicated account + gateway per partition"
    elif iso == "contractual" or "export-controlled" in classes:
        partition = "Partitioned — dedicated domain gateway (and policy engine); export-controlled tools on a separate gateway"
    else:
        partition = "Pooled — shared domain gateway, partition from JWT claim, Cedar + backend scope checks"
    if ctx.get("partition_dimension", "none") == "none":
        partition = "Not partitioned — single trust domain"

    # Q5
    if ctx.get("vendor_mcp_available"):
        server = "Reuse vendor MCP server behind the Gateway with a tool allow-list and capability-drift detection"
    elif ctx.get("needs_stateful_sessions") or any(t.get("target_type") == "runtime" for t in tools):
        server = "Build a custom MCP server on AgentCore Runtime (stateful sessions / long-running jobs)"
    else:
        server = "Wrap existing system APIs as Lambda/OpenAPI targets exposing curated business verbs"

    # Inbound auth
    auths = {c.get("auth") for c in consumers}
    inbound = "CUSTOM_JWT" if "jwt" in auths or ctx.get("user_delegation_to_saas") else "AWS_IAM (SigV4)"
    if auths == {"jwt", "sigv4"}:
        gates.append("Mixed JWT and SigV4 consumers: use separate gateways or confirm a single inbound type covers both.")

    # Standard open gates
    gates += [
        f"Confirm Gateway + Policy availability in {region} on the official AgentCore Regions page.",
        "Verify how trusted partition context reaches each target type (header forwarding or interceptor) and that forged context is rejected.",
        "Confirm Policy behaviour on service errors (not just Cedar deny) before relying on default-deny alone.",
        "Confirm gateway execution-role granularity per target; prefer separate gateways per trust domain.",
        "Check the published AgentCore SLA and set SLOs; time a cross-Region IaC redeploy drill to measure RTO.",
    ]
    if top == "T3":
        gates.append("Approval workflow, idempotency store and reconciliation job exist and pass the duplicate-write test.")

    return {
        "q1": q1, "plane": plane, "scores": scores, "weights": weights, "inbound": inbound,
        "partition": partition, "server": server, "tools": per_tool, "max_tier": top,
        "gates": gates, "rationale": rationale,
    }


def to_markdown(spec: dict, d: dict) -> str:
    mcp = spec.get("mcp") or {}
    ctx = spec.get("context") or {}
    today = dt.date.today().isoformat()
    lines = [
        f"# ADR: Governance and hosting for the `{mcp.get('name')}` MCP server",
        "",
        f"- **Status:** Proposed ({today})",
        f"- **Domain:** {mcp.get('domain')} · **Business owner:** {mcp.get('business_owner')} · "
        f"**Technical owner:** {mcp.get('technical_owner')} · **Risk owner:** {mcp.get('risk_owner') or 'n/a'}",
        f"- **Highest tool tier:** {d['max_tier']}",
        "",
        "## Context",
        "",
        mcp.get("purpose", ""),
        "",
        f"Hosting {ctx.get('hosting')}, primary Region {ctx.get('primary_region')}, IdP {ctx.get('identity_provider')}, "
        f"partition dimension {ctx.get('partition_dimension')}, isolation {ctx.get('isolation_requirement')}, "
        f"compliance {', '.join(ctx.get('compliance') or []) or 'none declared'}.",
        "",
        "## Decision",
        "",
        "| Question | Outcome |",
        "| --- | --- |",
        f"| Q1 MCP or not | {d['q1']} |",
        f"| Q2 Control plane | **{d['plane']}** — inbound auth {d['inbound']} |",
        f"| Q4 Partition model | {d['partition']} |",
        f"| Q5 Server strategy | {d['server']} |",
        "",
        "### Option scores (weighted, 1–5)",
        "",
        "| Option | Score |",
        "| --- | ---: |",
    ]
    for name, score in sorted(d["scores"].items(), key=lambda kv: -kv[1]):
        lines.append(f"| {name} | {score} |")
    lines += ["", "### Q3 Mandatory controls per tool", ""]
    for t in d["tools"]:
        lines.append(f"- **`{t['name']}`** ({t['tier']}, {t['target']} target)")
        for c in t["controls"]:
            lines.append(f"  - [ ] {c}")
    lines += ["", "## Rationale", ""] + [f"- {r}" for r in d["rationale"]]
    lines += [
        "",
        "## Responsibilities that stay with the application",
        "",
        "Gateway provides reachability and enforcement (authN, Cedar, rate limits, sessions, token vault). "
        "Business authorization, partition data isolation, human approval, idempotency and transactional "
        "correctness remain the domain team's responsibility.",
        "",
        "## Open verification gates (must close before this ADR is Accepted)",
        "",
    ] + [f"- [ ] {g}" for g in d["gates"]]
    lines += [
        "",
        "## Reconsideration triggers",
        "",
        "- A multi-cloud or portability mandate.",
        "- A required Region without AgentCore Policy.",
        "- A compliance finding against fail-open rate limiting.",
        "- Gateway-layer cost becoming material relative to cost per completed business task.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) != 1:
        print(__doc__)
        return 2
    spec = load_spec(args[0])
    result = decide(spec)
    print(json.dumps(result, indent=2) if "--json" in sys.argv else to_markdown(spec, result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
