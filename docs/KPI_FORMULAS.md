# KPI and SLA Formulas (InsightFlow)

## Time rules (one method, used everywhere)
- Timestamps are stored as naive **UTC** text (`YYYY-MM-DD HH:MM:SS`). No time-zone conversion is done; the UI shows UTC.
- SLA uses **calendar hours** (24x7). Weekends, holidays and business hours are **not** modelled.
- `due_at = created_at + SLA hours(priority)`. Defaults: Critical 4h, High 8h, Medium 24h, Low 72h (Admin can change; changes apply to new requests only).
- `resolved_at` is set the first time a request enters **Resolved** or **Closed**. Re-opening a request clears it.

| KPI | Formula | Empty case |
|---|---|---|
| Total requirements | `COUNT(requirements)` | 0 |
| Requirements by status / priority | `COUNT GROUP BY status, priority` | empty chart |
| Reqs missing acceptance criteria | requirements with no row in `acceptance_criteria` | 0 |
| Reqs without UAT tests | requirements with no row in `uat_tests` | 0 |
| Acceptance-criteria coverage % | `(total - missing) / total x 100` | n/a when total = 0 |
| UAT coverage % | `(total - without tests) / total x 100` | n/a |
| Open requests | status in New, Assigned, In Progress, Pending Info | 0 |
| Overdue requests | open AND `now > due_at` | 0 |
| Approaching deadline | open AND not overdue AND `due_at - now <= window` (default 8h) | 0 |
| Completed requests | requests with a `resolved_at` | 0 |
| **SLA compliance %** | `resolved with resolved_at <= due_at / resolved total x 100` | n/a when nothing resolved |
| **Average resolution time (h)** | `mean(resolved_at - created_at)` over resolved requests | n/a |
| Time in stage (h) | for each status-history row to an open stage: `next_event_time - this_event_time` (current stage uses `now`) | none if no history |
| Bottleneck stage | open stage with the highest **average** hours per visit | n/a |
| Compliance trend | SLA compliance % grouped by month of `resolved_at` (needs >= 2 months to chart) | message |

A request resolved exactly at its deadline counts as **met**.
Stage durations use only rows in `status_history`; nothing is estimated. Pending Info time is counted as stage time
(it is not paused from the SLA clock) - a documented simplification.
