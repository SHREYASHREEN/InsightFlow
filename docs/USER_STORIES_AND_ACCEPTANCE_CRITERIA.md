# Sample User Stories and Acceptance Criteria
Format: *As a [user], I want [capability], so that [business value].*

**US-001** As a service desk agent, I want to log a request with category and priority, so that every ticket can be triaged correctly.
- Given a logged-in agent, when they submit a request without a title, then the form shows "Title is required" and nothing is saved.

**US-002** As a service desk manager, I want the SLA deadline calculated automatically, so that I do not compute it by hand.
- Given a High priority request is created at 09:00, when it is saved, then its due time is 17:00 the same day (8 hours).

**US-003** As an operations head, I want to see overdue requests by owner, so that I can rebalance the workload.
- Given five requests are past their due time, when the manager opens the dashboard, then the Overdue KPI shows 5.

**US-004** As an HR business partner, I want to download the SLA summary as Excel, so that I can share it in the monthly review.
- Given any signed-in user, when they click "Full workbook (Excel)", then a .xlsx file with requests and SLA summary is downloaded.
