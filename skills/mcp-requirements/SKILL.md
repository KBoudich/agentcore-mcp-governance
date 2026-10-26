---
name: mcp-requirements
description: Capture requirements for a new MCP server and produce a validated mcp-spec.yaml (owners, consumers, data classes, systems of record, partition model, candidate tools, volume, SLOs). Use when someone wants to "create an MCP", "expose a system to agents", "build tools for an agent" or starts the mcp-architect lifecycle. Stage 1 of 7.
---

# MCP requirements intake (stage 1 · gate G0)

Goal: a complete `mcp-spec.yaml` that every later stage reads. Nothing is designed before G0 passes.

`<plugin>` is the mcp-architect root: the plugin directory in Claude Code, or `tools/mcp-architect/` when vendored with `scripts/install.py` (Codex, GitHub Copilot and other Agent Skills clients).

## Steps

1. **Copy the template** `templates/mcp-spec.template.yaml` (in this skill) to the owning repo as `mcp-spec.yaml`. For a worked example see `examples/industrial-quality-certificates/mcp-spec.yaml` at the plugin root.
2. **Interview, one block at a time.** Ask only what you cannot infer from the repo or the user's message. Prioritise:
   - *Purpose & owners* — the business outcome, the accountable business owner, technical owner, and (if any write is in scope) the risk owner who will sign T2/T3 tools.
   - *Consumers* — which agents or clients call it; user-delegated (JWT) or machine (SigV4); how many.
   - *Systems of record* — name, location (on-prem / aws / saas), interface, data classes. Flag `export-controlled`, `personal`, `restricted` early.
   - *Partitioning* — the dimension that must never leak (legal entity, plant, business unit, customer) and whether isolation is logical, contractual or regulatory.
   - *Candidate tools* — business **operations**, not capabilities. Push back on `run_sql`, `call_api`, `execute_*`, full-CRUD exposure. For each: side effect (none / reversible / consequential), inputs with constraints, expected response size, sync vs async.
   - *Volume* — users, interactions/day, tool calls and searches per interaction, peak TPS, egress.
   - *Operations* — SLO, RTO/RPO, on-call, retention.
3. **Assign a provisional tier** per tool by worst credible effect: T0 public read · T1 sensitive read · T2 reversible write · T3 consequential (financial, destructive, privilege-changing, external commitment). Bulk extraction of a T1 read can deserve T3.
4. **Validate:** `python3 <plugin>/scripts/validate_spec.py mcp-spec.yaml`. Fix every `ERROR`; list every `VERIFY` item as an open question in the spec's PR description.
5. **Hand off** to `mcp-governance-decision`.

## Rules

- Identity and partition values are **never** tool inputs. If a stakeholder asks for `entity_id` as an argument, record it as derived from the token context.
- Every write has an `idempotency_key` input and `idempotency: key`.
- Every T3 tool has `approval: required` and explicit `limits`.
- Write tool descriptions for the model: when to use, when not to, what it will not do.
- Mark assumptions explicitly (`# ASSUMPTION:` comments) instead of inventing facts about the organisation's systems.

## Output

`mcp-spec.yaml` with zero validator errors, committed for review by the business and technical owners.
