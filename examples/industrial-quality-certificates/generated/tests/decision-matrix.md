# Policy decision matrix — quality-certificates

Run against stage in LOG_ONLY, then ENFORCE, on every policy, schema or tool change. A Cedar allow is never evidence of business correctness: the backend column must also pass.

| # | Tool | Caller | Arguments | Expected tools/list | Expected tools/call | Backend expectation |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | `QualityCertificatesTools___get_inspection_certificate` | scope `quality/read` + legal_entity claim | valid | visible | allowed | returns own-legal_entity data only |
| 2 | `QualityCertificatesTools___get_inspection_certificate` | no `quality/read` scope | valid | hidden | denied (default deny) | not invoked |
| 3 | `QualityCertificatesTools___get_inspection_certificate` | scope ok, **missing** legal_entity claim | valid | hidden | denied | not invoked |
| 4 | `QualityCertificatesTools___get_inspection_certificate` | scope ok, legal_entity=A | record of legal_entity B | visible | allowed by Cedar | **rejects** (backend scope) |
| 5 | `QualityCertificatesTools___get_inspection_certificate` | scope ok | forged `legal_entity` / `_trusted_context` in arguments | visible | allowed | interceptor overwrites; backend ignores forged value |
| 6 | `QualityCertificatesTools___get_inspection_certificate` | any | break-glass forbid deployed | hidden | denied (forbid wins) | not invoked |
| 7 | `QualityCertificatesTools___list_open_nonconformances` | scope `quality/read` + legal_entity claim | valid | visible | allowed | returns own-legal_entity data only |
| 8 | `QualityCertificatesTools___list_open_nonconformances` | no `quality/read` scope | valid | hidden | denied (default deny) | not invoked |
| 9 | `QualityCertificatesTools___list_open_nonconformances` | scope ok, **missing** legal_entity claim | valid | hidden | denied | not invoked |
| 10 | `QualityCertificatesTools___list_open_nonconformances` | scope ok, legal_entity=A | record of legal_entity B | visible | allowed by Cedar | **rejects** (backend scope) |
| 11 | `QualityCertificatesTools___list_open_nonconformances` | scope ok | forged `legal_entity` / `_trusted_context` in arguments | visible | allowed | interceptor overwrites; backend ignores forged value |
| 12 | `QualityCertificatesTools___list_open_nonconformances` | any | break-glass forbid deployed | hidden | denied (forbid wins) | not invoked |
| 13 | `QualityCertificatesTools___create_nonconformance_draft` | scope `quality/write` + legal_entity claim | valid | visible | allowed | returns own-legal_entity data only |
| 14 | `QualityCertificatesTools___create_nonconformance_draft` | no `quality/write` scope | valid | hidden | denied (default deny) | not invoked |
| 15 | `QualityCertificatesTools___create_nonconformance_draft` | scope ok, **missing** legal_entity claim | valid | hidden | denied | not invoked |
| 16 | `QualityCertificatesTools___create_nonconformance_draft` | scope ok, legal_entity=A | record of legal_entity B | visible | allowed by Cedar | **rejects** (backend scope) |
| 17 | `QualityCertificatesTools___create_nonconformance_draft` | scope ok | forged `legal_entity` / `_trusted_context` in arguments | visible | allowed | interceptor overwrites; backend ignores forged value |
| 18 | `QualityCertificatesTools___create_nonconformance_draft` | scope ok | same idempotency_key twice | visible | allowed | second call returns first result, no duplicate write |
| 19 | `QualityCertificatesTools___create_nonconformance_draft` | any | break-glass forbid deployed | hidden | denied (forbid wins) | not invoked |
| 20 | `QualityCertificatesTools___request_quality_hold_release` | scope `quality/propose` + legal_entity claim | valid | visible | allowed | returns own-legal_entity data only |
| 21 | `QualityCertificatesTools___request_quality_hold_release` | no `quality/propose` scope | valid | hidden | denied (default deny) | not invoked |
| 22 | `QualityCertificatesTools___request_quality_hold_release` | scope ok, **missing** legal_entity claim | valid | hidden | denied | not invoked |
| 23 | `QualityCertificatesTools___request_quality_hold_release` | scope ok, legal_entity=A | record of legal_entity B | visible | allowed by Cedar | **rejects** (backend scope) |
| 24 | `QualityCertificatesTools___request_quality_hold_release` | scope ok | forged `legal_entity` / `_trusted_context` in arguments | visible | allowed | interceptor overwrites; backend ignores forged value |
| 25 | `QualityCertificatesTools___request_quality_hold_release` | scope ok | same idempotency_key twice | visible | allowed | second call returns first result, no duplicate write |
| 26 | `QualityCertificatesTools___request_quality_hold_release` | scope ok | valid, no approval yet | visible | allowed | creates PENDING approval only; nothing executed |
| 27 | `QualityCertificatesTools___request_quality_hold_release` | any | break-glass forbid deployed | hidden | denied (forbid wins) | not invoked |
