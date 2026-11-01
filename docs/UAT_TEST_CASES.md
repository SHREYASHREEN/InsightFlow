# Sample UAT Test Cases
| ID | Requirement | Steps | Expected result |
|---|---|---|---|
| UAT-001 | REQ-001 | Requests -> New request, leave title empty, submit | Error "Title is required" |
| UAT-002 | REQ-002 | Create a High request; read its due time in All requests | due_at = created_at + 8 hours |
| UAT-003 | REQ-003 | Update a request status, open its history table | New history row with old/new status and time |
| UAT-004 | REQ-004 | Open Requests and SLA -> Dashboard | Overdue KPI equals rows in the Overdue list |
| UAT-005 | Login | Sign in with wrong password | "Invalid username or password" |
| UAT-006 | RBAC | Sign in as viewer | No Administration menu; cannot see create forms |
| UAT-007 | Import | Upload sample_data/sample_requirements_import_with_errors.csv | 1 imported; duplicates/invalid rows listed |
| UAT-008 | Export | Download Excel workbook and open it | Sheets contain current data; cells starting with = are prefixed with ' |
