# Tool contract rules

## 1. Curate operations, not capabilities

| Avoid | Prefer | Why |
| --- | --- | --- |
| `run_sql(query)` | `list_open_nonconformances(plant_code, page_token)` | Cedar can reason about a plant code; it cannot reason about SQL |
| `call_sap(service, payload)` | `get_inspection_certificate(order_number, item_number)` | one effect, one owner, one test matrix |
| `update_po(po)` (full object) | `create_po_draft(...)` + `request_po_approval(po_id, amount)` | authority split by tier |
| `release_hold(batch)` | `request_quality_hold_release(batch_id, disposition, justification, idempotency_key)` | T3 proposes; humans release |

Narrow tools increase catalogue size; share implementation libraries, not generic exposed capabilities.

## 2. Schema rules (AgentCore Lambda target format)

- Top level `inputSchema` is `type: object` with `properties` and `required`.
- Property types: `string`, `number`, `integer`, `boolean`, `array` (`items`), `object` (`properties`, `required`). No `enum`, `pattern` or `format` keywords — put constraints in `description` and enforce them in the adapter.
- Tool names appear to agents as `<TargetName>___<tool>`; the total must stay ≤ 256 characters.
- Inline schemas ≤ 1 MB; S3 schemas ≤ 10 MB. Payloads (call/list/search) ≤ 6 MB.

## 3. Description template

```
<What it returns or does, in one sentence, naming the business object.>
Use when <situation>. Do not use for <bulk export / other partitions / releasing>.
<Constraint the model must respect, e.g. "Requires an order number from the customer.">
```

## 4. Idempotency contract

```
claim(pk = caller + tool + idempotency_key, intent_hash)
  new            -> execute, store result, mark DONE
  exists, same intent, DONE        -> return stored result
  exists, same intent, IN_PROGRESS -> "outcome unknown, reconciliation pending" (no retry)
  exists, different intent         -> reject
```

A gateway timeout does not mean the tool did not run. Reconcile against the system of record before any retry.

## 5. Approval contract (T3)

The approval record binds: requester (`sub`), partition, tool, canonical intent (arguments hash), limits evaluated, expiry, required approver entitlement. At execution: re-check approver entitlement, record state (e.g. batch still on hold), expiry, and that the intent hash matches. Approval is never inferred from a Cedar allow.

## 6. Async pattern

`submit_<job>` → `{job_id, status: QUEUED}`; `get_<job>_status(job_id)` → `{status, result?}`. Use AgentCore Runtime targets for jobs up to 8 h; keep sync calls well under the 15-minute gateway timeout and the 5,000 concurrent-connection quota.

## 7. Change classification

| Change | Class | Required |
| --- | --- | --- |
| New optional input with tight constraint | additive | schema review |
| Widened enum / relaxed bound / new output field / new endpoint | authority expansion | re-tier, security review, Cedar regeneration, decision-matrix rerun |
| Description edit | executable influence | review like code |
| Removal / rename | breaking | deprecation window with named consumers |
