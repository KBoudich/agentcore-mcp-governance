---
name: mcp-governance-decision
description: Apply the MCP governance decision framework to an mcp-spec.yaml and write an ADR — is MCP the right interface, which control plane (AgentCore Gateway, self-managed gateway, direct MCP, app endpoints), risk tier and mandatory controls per tool, partition model (pooled / partitioned / siloed), build vs wrap vs reuse the server. Use when deciding how to govern or host an MCP server, comparing gateway options, or preparing a Design Authority review. Stage 2 of 7.
---

# Governance decision (stage 2 · gate G1)

Read `references/decision-framework.md` (this skill) before answering — it holds the questions, knock-outs, weights and the rationale for each default.

## Steps

1. Ensure `mcp-spec.yaml` passes `validate_spec.py` (stage 1).
2. Run the engine: `python3 <plugin>/scripts/decide.py mcp-spec.yaml > docs/adr-NNNN-<name>-governance.md`
   (`--json` gives the raw result for further reasoning).
3. **Review the output critically — the script is a starting point, not the decision.** Check in particular:
   - Q1: is a plain API + framework tool adapter simpler for this case?
   - Q2: did a knock-out apply (portability mandate, Region without AgentCore Policy, tiny T0-only server)? If the user's context changes the weights (e.g. a strong multi-cloud strategy), say so and adjust.
   - Q4: does the partition model match contracts (JV, export control, customer-specific data)?
   - Q5: if a vendor MCP server exists, it still goes **behind** the gateway with a tool allow-list and drift detection.
4. Complete the ADR sections the script cannot know: named people, exceptions with expiry, compensating controls, and the reconsideration triggers that matter for this organisation.
5. Route for approval: Design Authority for every server; the **risk owner signs** every T2/T3 tool and its limits. Authors never approve their own authority increase.

## Non-negotiables to restate in every ADR

- Gateway solves **reachability and enforcement**. Business authorization, partition isolation, approvals, idempotency and transactional correctness stay with the domain team.
- Rate limits are consumption control and fail open on transient errors — never a security or isolation control.
- Cedar decides *tool + arguments for a principal*; it does not know who owns record #123.
- Policy evaluation covers MCP tools; prompts and resources are always allowed — disable or protect them at the target.

## Output

An ADR in `Proposed` state with a checklist of mandatory controls per tool and open verification gates. It becomes `Accepted` only when every gate is closed with evidence.
