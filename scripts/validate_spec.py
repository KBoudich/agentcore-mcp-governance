#!/usr/bin/env python3
"""Validate an mcp-spec against the governance rules of the mcp-architect plugin.

    validate_spec.py mcp-spec.yaml [--json]

Exit code 0 = no errors (warnings allowed), 1 = errors, 2 = usage.
Errors block promotion (gates G0-G2); warnings are verification gates to close.
"""

from __future__ import annotations

import json
import re
import sys

from spec_io import load_reference, load_spec

TIERS = ["T0", "T1", "T2", "T3"]
SIDE_EFFECT_MIN_TIER = {"none": "T0", "reversible": "T2", "consequential": "T3"}
SENSITIVE_CLASSES = {"confidential", "restricted", "personal", "export-controlled"}
TARGETS = {"lambda", "openapi", "mcp_server", "runtime", "http_passthrough", "smithy", "api_gateway"}
GENERIC_VERBS = re.compile(
    r"^(run|exec|execute|query|call|invoke|proxy|admin|do|perform)(_|$)|(_sql|_any|_raw|_query|_command)$"
)
NAME_RE = re.compile(r"^[a-z][a-z0-9_]{2,63}$")
IDENTITY_INPUTS = {"user_id", "tenant_id", "entity_id", "legal_entity", "username", "email", "sub", "role", "roles"}


def _tier_at_least(tier: str, minimum: str) -> bool:
    return TIERS.index(tier) >= TIERS.index(minimum)


def validate(spec: dict) -> tuple[list[str], list[str]]:
    facts = load_reference("agentcore-facts.json")
    errors: list[str] = []
    warnings: list[str] = []

    mcp = spec.get("mcp") or {}
    ctx = spec.get("context") or {}
    tools = spec.get("tools") or []
    volume = spec.get("volume") or {}

    # G0 — ownership and context
    for key in ("name", "domain", "purpose", "business_owner", "technical_owner"):
        if not mcp.get(key):
            errors.append(f"G0 mcp.{key} is required")
    if mcp.get("name") and not re.match(r"^[a-z][a-z0-9-]{2,62}$", mcp["name"]):
        errors.append("G0 mcp.name must be kebab-case (3-63 chars)")
    if not spec.get("consumers"):
        errors.append("G0 at least one consumer is required (who calls this server?)")
    if not tools:
        errors.append("G0 at least one tool is required")
    if not spec.get("systems_of_record"):
        warnings.append("G0 no systems_of_record declared — data classification cannot be checked")

    sor_names = {s.get("name") for s in spec.get("systems_of_record") or []}
    partition_dim = ctx.get("partition_dimension", "none")
    region = ctx.get("primary_region", "")

    # Region gates
    if ctx.get("hosting", "aws") == "aws":
        if region in facts["regions"]["gateway_without_policy_reported"]:
            errors.append(
                f"G4 primary_region {region} is reported without AgentCore Policy — choose a Policy Region "
                f"(e.g. eu-central-1) or justify deferral of T1+ tools"
            )
        elif region not in facts["regions"]["policy_reported"]:
            warnings.append(f"G4 verify AgentCore Gateway + Policy availability in {region or '<unset>'} on the official Regions page")
        else:
            warnings.append(f"G4 Policy reported in {region} by a third-party snapshot — confirm on the official Regions page")

    if ctx.get("user_delegation_to_saas"):
        auth_kinds = {c.get("auth") for c in spec.get("consumers") or []}
        if auth_kinds == {"sigv4"}:
            errors.append("G1 3LO user delegation requires JWT inbound: IAM (SigV4) inbound is rejected when a target uses 3LO OAuth")

    has_high_tier = False
    names = set()
    for i, tool in enumerate(tools):
        label = tool.get("name") or f"tools[{i}]"
        name = tool.get("name", "")
        if not NAME_RE.match(name):
            errors.append(f"G2 {label}: tool name must be snake_case verb_noun (3-64 chars)")
        if name in names:
            errors.append(f"G2 {label}: duplicate tool name")
        names.add(name)
        if GENERIC_VERBS.search(name):
            errors.append(f"G2 {label}: generic capability verb — expose a bounded business operation instead")
        if len(mcp.get("name", "")) + 3 + len(name) > facts["quotas"]["tool_name_max_chars"]:
            errors.append(f"G2 {label}: Target___tool name exceeds 256 characters")
        if len(tool.get("description", "")) < 40:
            errors.append(f"G2 {label}: description must tell the model when to use and when not to (>= 40 chars)")

        tier = tool.get("tier")
        side = tool.get("side_effect", "none")
        if tier not in TIERS:
            errors.append(f"G1 {label}: tier must be one of {TIERS}")
            continue
        if side not in SIDE_EFFECT_MIN_TIER:
            errors.append(f"G1 {label}: side_effect must be none | reversible | consequential")
            continue
        if not _tier_at_least(tier, SIDE_EFFECT_MIN_TIER[side]):
            errors.append(f"G1 {label}: side_effect={side} requires tier >= {SIDE_EFFECT_MIN_TIER[side]} (got {tier})")
        classes = set(tool.get("data_classes") or [])
        if classes & SENSITIVE_CLASSES and tier == "T0":
            errors.append(f"G1 {label}: sensitive data classes {sorted(classes & SENSITIVE_CLASSES)} cannot be T0")
        if "export-controlled" in classes:
            warnings.append(f"G1 {label}: export-controlled data — confirm screening and consider a partitioned gateway")
        if _tier_at_least(tier, "T2"):
            has_high_tier = True

        # Writes
        if side != "none":
            if tool.get("idempotency") != "key":
                errors.append(f"G2 {label}: writes require idempotency: key")
            if not any(inp.get("name") == "idempotency_key" for inp in tool.get("inputs") or []):
                errors.append(f"G2 {label}: writes require an idempotency_key input")
        if tier == "T3":
            if tool.get("approval") != "required":
                errors.append(f"G1 {label}: T3 requires approval: required (bound to the exact intent)")
            if not tool.get("limits"):
                errors.append(f"G1 {label}: T3 requires explicit business limits")
        if tier == "T2" and tool.get("approval") == "none":
            warnings.append(f"G1 {label}: T2 with no approval — confirm compensation path is proven")

        # Partition / identity
        if tool.get("partition_scoped") and partition_dim in ("none", "", None):
            errors.append(f"G1 {label}: partition_scoped tool but context.partition_dimension is none")
        if classes & SENSITIVE_CLASSES and not tool.get("partition_scoped") and partition_dim not in ("none", "", None):
            warnings.append(f"G1 {label}: sensitive data without partition_scoped — confirm data is not entity-specific")
        for inp in tool.get("inputs") or []:
            if (inp.get("name") or "").lower() in IDENTITY_INPUTS:
                errors.append(
                    f"G3 {label}: input '{inp['name']}' looks like identity/partition — take it from the validated token context, never from model arguments"
                )
            if inp.get("type") == "string" and not inp.get("constraints"):
                warnings.append(f"G2 {label}.{inp.get('name')}: unconstrained string input")

        # Target type
        target = tool.get("target_type")
        if target not in TARGETS:
            errors.append(f"G2 {label}: target_type must be one of {sorted(TARGETS)}")
        else:
            tc = facts["target_constraints"][target]
            sor = next((s for s in spec.get("systems_of_record") or [] if s.get("name") == tool.get("system_of_record")), None)
            if sor and sor.get("location") in ("on-prem", "aws") and not tc["private_endpoint"]:
                errors.append(f"G4 {label}: {target} target cannot reach private systems — {tc['note']}")
            if target in ("runtime", "http_passthrough"):
                warnings.append(f"G3 {label}: verify Policy coverage for the {target} route before relying on Cedar")
        if tool.get("system_of_record") and tool["system_of_record"] not in sor_names:
            errors.append(f"G0 {label}: system_of_record '{tool['system_of_record']}' not declared")

        # Response bounds
        max_kb = tool.get("max_response_kb", 0)
        if not max_kb:
            errors.append(f"G2 {label}: max_response_kb required (paginate and cap)")
        elif max_kb > facts["quotas"]["max_payload_mb"] * 1024:
            errors.append(f"G2 {label}: max_response_kb exceeds the 6 MB payload quota")
        if tool.get("execution") == "sync" and side == "consequential":
            warnings.append(f"G2 {label}: consequential write is sync — prefer submit + poll")

    if has_high_tier and not mcp.get("risk_owner"):
        errors.append("G1 mcp.risk_owner is required when any tool is T2 or T3")

    # Volume / quota envelope
    if volume:
        calls_per_month = (
            volume.get("users", 0) * volume.get("interactions_per_user_per_day", 0)
            * volume.get("working_days_per_month", 22) * volume.get("tool_calls_per_interaction", 0)
        )
        searches_per_min_avg = (
            volume.get("users", 0) * volume.get("interactions_per_user_per_day", 0)
            * volume.get("searches_per_interaction", 0) / (8 * 60)
        )
        if searches_per_min_avg > facts["quotas"]["search_calls_per_minute"]:
            warnings.append(
                f"G4 average ~{searches_per_min_avg:.0f} searches/min over an 8 h day exceeds the default 25/min search quota — cache tools/list or request an increase"
            )
        if volume.get("peak_tps", 0) > facts["quotas"]["tool_call_tps_gateway"] * 0.5:
            warnings.append("G4 peak TPS above 50% of the default 200 TPS gateway quota (shared at account level) — plan a quota increase")
        if calls_per_month == 0:
            warnings.append("G4 volume block present but yields zero tool calls")
    else:
        warnings.append("G4 no volume block — cost and quota envelope cannot be checked")

    if len(tools) > facts["quotas"]["tools_per_target"]:
        errors.append("G2 more than 1,000 tools on one target")
    return errors, warnings


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) != 1:
        print(__doc__)
        return 2
    errors, warnings = validate(load_spec(args[0]))
    if "--json" in sys.argv:
        print(json.dumps({"errors": errors, "warnings": warnings}, indent=2))
    else:
        for e in errors:
            print(f"ERROR   {e}")
        for w in warnings:
            print(f"VERIFY  {w}")
        print(f"\n{len(errors)} error(s), {len(warnings)} verification item(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
