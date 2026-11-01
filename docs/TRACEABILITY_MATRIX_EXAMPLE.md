# Traceability Matrix - example (matches the seeded sample data)
| Objective | Requirement | User story | Acceptance criterion | UAT test | UAT status |
|---|---|---|---|---|---|
| OBJ-02 | REQ-001 Log a request with mandatory fields | US-001 | Given a logged-in agent, when they submit without a title, then an error is shown | UAT-001 | Passed |
| OBJ-02 | REQ-002 Auto SLA deadline | US-002 | Given a High request created at 09:00, when saved, then due time is 17:00 | UAT-002 | Not Run |
| OBJ-01 | REQ-003 Record status changes | - | Each status change creates one history row | UAT-003 | Passed |
| OBJ-03 | REQ-004 Overdue dashboard | US-003 | Given 5 overdue requests, when manager opens dashboard, then Overdue KPI shows 5 | UAT-004 | Failed |
| OBJ-03 | REQ-006 Export SLA summary | US-004 | - (gap) | - (gap) | - |
Gaps in the sample: REQ-005/006/007/008 lack acceptance criteria or tests; OBJ-04 has no requirements; REQ-008 has no objective.
The live version is on the **Traceability** page and is generated from the database.
