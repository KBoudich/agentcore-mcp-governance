# Runbooks

| Incident | Detect | Respond | Close |
| --- | --- | --- | --- |
| Throttling (429) | throttle metrics by dimension | identify which bucket (partition, user, tool, account quota); customer limits AND with service quotas; raise the specific bucket, cache `tools/list`, reduce search calls | root cause: chatty discovery, retries, quota plan |
| Downstream timeout | adapter latency, gateway 5xx | distinguish client abort vs target still running; **do not retry writes**; reconcile idempotency records in `IN_PROGRESS` against the system of record | reconciliation report; async pattern if recurring |
| Expired / revoked SaaS credentials | outbound auth failures | Identity refreshes automatically; on provider-side revocation trigger re-consent (`forceAuthentication`) | user re-authorised; no stale tokens |
| Policy denial storm | deny spike for one tool/principal set | compare with last policy release; check an over-broad `forbid` or a claim-mapping change at the IdP; roll back via pipeline (prod engine stays ENFORCE) | decision-matrix rerun green |
| Catalogue drift | registry vs `tools/list` diff | unknown tools have no permit (hidden + denied); quarantine target sync; review vendor change | registry updated with tier + owner |
| Suspected cross-partition leakage | backend rejection spike, audit query, report | deploy targeted forbid for the tool (break-glass), disable adapter route (kill switch), preserve evidence, audit queries for affected partitions; `rate=0` only as an additional mute | security incident process; re-enter through G3–G6 |
| Emergency tool shutdown | any | `workflow_dispatch breakglass_tool=<tool>` (prod approval), confirm tool hidden and calls denied, notify consumers | forbid removed only after root cause and gate rerun |
| Approval backlog / expiry | pending approvals metric | notify approvers; expired approvals cannot execute — requester resubmits | SLA review with risk owner |
