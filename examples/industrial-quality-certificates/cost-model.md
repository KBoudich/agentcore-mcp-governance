# Gateway-layer cost — quality-certificates (rates verified 2026-10-21)

## Scale x1: 52,800 interactions/month, 211,200 tool calls

| Meter | USD / month |
| --- | ---: |
| Search API | 1.32 |
| Gateway invocations | 1.06 |
| Policy authorizations | 5.28 |
| Tool indexing | 0.00 |
| VPC egress | 0.72 |
| **Total gateway layer** | **8.38** |

## Scale x10: 528,000 interactions/month, 2,112,000 tool calls

| Meter | USD / month |
| --- | ---: |
| Search API | 13.20 |
| Gateway invocations | 10.56 |
| Policy authorizations | 52.80 |
| Tool indexing | 0.00 |
| VPC egress | 7.20 |
| **Total gateway layer** | **83.76** |

> Quota: ~50 searches/min average exceeds the default 25/min — request an increase or cache tools/list.

Policy checks cost 5x an invocation; retries and re-listing multiply every meter. Manage cost per completed business task, not this subtotal.
