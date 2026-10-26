#!/usr/bin/env python3
"""Gateway-layer monthly cost estimate from an mcp-spec volume block.

    cost_model.py mcp-spec.yaml [--scale 1,5,25]

Rates come from reference/agentcore-facts.json (dated). This is NOT total cost of
ownership: add target compute, interceptor invocations, CloudWatch, IdP, private
connectivity beyond the egress meter and model inference per completed task.
"""

from __future__ import annotations

import sys

from spec_io import load_reference, load_spec


def estimate(volume: dict, n_tools: int, rates: dict, factor: float = 1.0) -> dict:
    interactions = (volume.get("users", 0) * volume.get("interactions_per_user_per_day", 0)
                    * volume.get("working_days_per_month", 22) * factor)
    calls = interactions * volume.get("tool_calls_per_interaction", 0)
    searches = interactions * volume.get("searches_per_interaction", 0)
    policy = calls * volume.get("policy_checks_per_call", 1)
    egress = volume.get("egress_gb_per_month", 0) * factor
    lines = {
        "Search API": searches * rates["search_per_million"] / 1e6,
        "Gateway invocations": calls * rates["gateway_invocation_per_million"] / 1e6,
        "Policy authorizations": policy * rates["policy_authorization_per_request"],
        "Tool indexing": max(n_tools, 1) / 100 * rates["tool_indexing_per_100_tools_month"],
        "VPC egress": egress * rates["vpc_egress_per_gb"],
    }
    return {"interactions": interactions, "calls": calls, "searches": searches, "lines": lines,
            "total": sum(lines.values())}


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) != 1:
        print(__doc__)
        return 2
    scales = [1.0]
    for a in sys.argv[1:]:
        if a.startswith("--scale"):
            scales = [float(x) for x in a.split("=", 1)[1].split(",")]
    spec = load_spec(args[0])
    facts = load_reference("agentcore-facts.json")
    rates = facts["pricing_usd"]
    n_tools = len(spec.get("tools") or [])
    vol = spec.get("volume") or {}

    print(f"# Gateway-layer cost — {spec.get('mcp', {}).get('name')} (rates verified {facts['verified_on']})\n")
    for f in scales:
        r = estimate(vol, n_tools, rates, f)
        print(f"## Scale x{f:g}: {r['interactions']:,.0f} interactions/month, {r['calls']:,.0f} tool calls\n")
        print("| Meter | USD / month |\n| --- | ---: |")
        for k, v in r["lines"].items():
            print(f"| {k} | {v:,.2f} |")
        print(f"| **Total gateway layer** | **{r['total']:,.2f}** |\n")
        searches_per_min = r["searches"] / (vol.get("working_days_per_month", 22) * 8 * 60) if r["searches"] else 0
        if searches_per_min > facts["quotas"]["search_calls_per_minute"]:
            print(f"> Quota: ~{searches_per_min:.0f} searches/min average exceeds the default 25/min — request an increase or cache tools/list.\n")
    print("Policy checks cost 5x an invocation; retries and re-listing multiply every meter. "
          "Manage cost per completed business task, not this subtotal.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
