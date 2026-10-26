---
name: mcp-tool-design
description: Design safe MCP tool contracts for business systems — bounded business verbs, JSON input schemas the gateway accepts, descriptions written for the model, pagination and size caps, idempotency keys, async submit+poll, and approval bound to exact intent. Use when writing or reviewing MCP tool definitions, tool schemas, or when a tool exposes generic SQL/API/CRUD capability. Stage 3 of 7.
---

# Tool design (stage 3 · gate G2)

Read `references/tool-contract-rules.md` (this skill) for the full rule set and examples.

## Steps

1. For each tool in `mcp-spec.yaml`, rewrite it as a **bounded business command**: `verb_noun`, one business effect, the smallest input surface. Split tools whose authority differs (read vs draft vs release).
2. Tighten inputs: every string gets a pattern, enum or max length; numbers get ranges; IDs are typed. Remove identity/partition inputs — they come from the trusted context.
3. Write the description for the model: what it does, when to use it, when **not** to, what it never does (e.g. "never releases directly").
4. Writes: add `idempotency_key` (uuid) and define the duplicate rule: same key + same intent → same result; same key + different intent → reject; unknown prior outcome → reconcile, never blind retry.
5. Long work (> a few seconds or > 15 min gateway timeout risk): `execution: async` with `submit_*` returning a job id and `get_*_status` to poll.
6. T3: the tool **proposes**; it creates an approval bound to who, what, amounts, partition and expiry. Execution happens only after an entitled approver signs that exact intent — re-check entitlement and record state at execution time.
7. Responses: paginate (`page_token`), cap (`max_results`, `max_response_kb` ≪ 6 MB), minimise fields, never echo secrets or other partitions' data.
8. Re-run `validate_spec.py`, then `scaffold_deploy.py` (stage 6) generates the gateway tool schemas from the spec — the spec stays the single source of truth.

## Review checklist

- [ ] No generic verbs (`run_`, `execute_`, `query_`, `_sql`, `_any`, admin wrappers)
- [ ] No identity or partition fields in inputs
- [ ] Every string constrained; enums listed in the description (the Lambda schema format has no `enum` keyword — the adapter validates)
- [ ] Writes idempotent; T3 approval-bound; async where long
- [ ] Response capped and paginated
- [ ] Description reviewed as *executable influence* (it steers model selection; no credentials or tenant examples)
- [ ] Schema change classified: additive vs authority-expanding (widened enum, relaxed bound, new output field ⇒ re-review)
