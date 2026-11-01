# Functional Requirements Document (FRD) - SAMPLE
| ID | Requirement | Type | Priority | Objective |
|---|---|---|---|---|
| FR-01 | Users sign in with username and password; invalid attempts show a clear error | Functional | High | OBJ-03 |
| FR-02 | Access to pages and actions depends on role (Admin / Business Analyst / Viewer) | Non-Functional (security) | High | OBJ-03 |
| FR-03 | Analysts can create, edit and search requirements; IDs must be unique | Functional | High | OBJ-01 |
| FR-04 | Each requirement edit is logged with old and new value | Functional | Medium | OBJ-03 |
| FR-05 | Requests get an SLA due time from their priority | Functional | Critical | OBJ-02 |
| FR-06 | Every request status change is stored with a timestamp | Functional | High | OBJ-01 |
| FR-07 | Dashboard shows open, overdue, SLA %, average resolution time | Functional | High | OBJ-03 |
| FR-08 | Traceability matrix highlights requirements lacking criteria or tests | Functional | Medium | OBJ-03 |
| FR-09 | Reports export to CSV, Excel and Markdown; text cells starting with = + - @ are neutralised | Functional | Medium | OBJ-03 |
| FR-10 | CSV import validates columns/values and reports duplicates and errors | Functional | Medium | OBJ-01 |
| NFR-01 | Passwords stored only as salted scrypt hashes | Non-Functional | High | - |
| NFR-02 | All SQL uses bound parameters | Non-Functional | High | - |
| NFR-03 | Core pages respond within a few seconds for a few thousand rows (not load-tested) | Non-Functional | Low | - |
