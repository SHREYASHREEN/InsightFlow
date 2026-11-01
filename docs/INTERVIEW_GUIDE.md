# InsightFlow - Interview and Viva Guide

## 1. The business problem
A service desk has requests but no consistent view of deadlines, ownership and where tickets wait; requirements are scattered and nobody can prove each one has acceptance criteria and a test. InsightFlow gives one place for both.

## 2. Why useful / who uses it
Business analysts (document and trace requirements), service-desk managers (SLA and bottlenecks), stakeholders/viewers (read-only reports). It demonstrates BA artefacts, SQL-backed KPIs and reporting.

## 3. Stack and why
Python (readable, you know it) - Streamlit (fast data apps, no front-end code) - SQLite (zero-setup relational DB, supports foreign keys) - pandas (tables, exports) - Plotly (interactive charts) - openpyxl (Excel writer) - scrypt from `hashlib` (secure password hashing without extra installs) - unittest/pytest (tests).

## 4. Where to study (file -> functions)
| Topic | File | Functions |
|---|---|---|
| Schema and foreign keys | `insightflow/db.py` | `connect`, `init_db`, `SCHEMA` |
| Passwords / login | `insightflow/auth.py` | `hash_password`, `verify_password`, `authenticate`, `create_user` |
| RBAC | `insightflow/auth.py` | `PERMISSIONS`, `has_permission`; used in `ui.py` and `app.py` |
| Requirement rules | `requirements_service.py` | `validate_requirement`, `create_requirement`, `update_requirement`, `list_requirements` |
| Traceability | `traceability.py` | `build_matrix`, `gap_report`, `coverage_summary` |
| SLA / bottleneck | `sla.py` | `create_request`, `change_status`, `sla_summary`, `stage_durations`, `bottleneck_analysis` |
| Import / export | `imports.py`, `exports.py` | `import_requirements_csv`, `sanitize_cell`, `dfs_to_excel_bytes` |
| Tests | `tests/test_core.py` | one class per module |

## 5. Authentication flow
Login form -> `auth.authenticate(conn, username, password)` -> looks up user, runs `verify_password` (scrypt with stored salt, compared using `hmac.compare_digest`) -> returns a small user dict -> stored in `st.session_state["user"]`. `app.py` shows the login page when that key is missing. Same error message for unknown user and wrong password so attackers cannot discover usernames. Logout removes the key.

## 6. RBAC
`PERMISSIONS` maps role -> set of permission strings. UI code calls `auth.has_permission(role, "requirement.write")` before showing forms; `app.py` also re-checks before running a page (defence in depth). Admin-only: delete, users, settings.

## 7. Key SQL ideas
- Traceability uses `LEFT JOIN` chain so missing links appear as NULL (gaps).
- Gaps use `NOT EXISTS (SELECT 1 FROM ... WHERE requirement_id = r.id)`.
- Status counts use `GROUP BY status`.
- All values are passed as `?` parameters (never string-built) to prevent SQL injection; the only dynamic piece, the sort column, is looked up in a whitelist dictionary.

## 8. KPI calculation (see docs/KPI_FORMULAS.md)
SLA compliance % = resolved on time / resolved total x 100. Average resolution = mean(resolved_at - created_at). Stage time = difference between consecutive `status_history` timestamps.

## 9. Dashboard data flow
`ui.page_overview` -> `kpis.overview(conn)` -> `sla.sla_summary` + SQL counts -> dict -> `kpi_card` and Plotly figures. Nothing is hard-coded.

## 10. Import / export
Import: pandas reads CSV as text, checks required columns, then each row goes through the same `create_requirement` validation as the form; duplicates are skipped and listed. Export: pandas DataFrame -> CSV bytes / Excel bytes; `sanitize_cell` prefixes `'` to text beginning with `= + - @` so Excel will not run it as a formula (CSV/formula injection).

## 11. How tests verify correctness
Tests build an in-memory SQLite DB, insert known data and assert exact results - e.g. a High request created 09:00 resolved 15:00 must be on time, average 6h; 1 of 2 resolved on time = 50.0%. Edge cases: empty DB returns None, deadline exactly met counts as met, duplicate IDs rejected, invalid CSV rows counted.

## 12. Limitations / future work
See `KNOWN_LIMITATIONS.md`. Future: business-hours calendar, email notifications, comments on requirements, PostgreSQL, audit log for all tables, SSO, Power BI export.

## 13. Business-analysis concepts in plain words
- **Business requirement**: what the business needs and why ("improve SLA compliance to 90%").
- **Functional requirement**: what the system must do ("calculate due time from priority").
- **Non-functional requirement**: how well it must work (security, speed, usability).
- **User story**: As a [user], I want [capability], so that [value].
- **Acceptance criteria**: testable conditions for "done"; Given/When/Then style.
- **Traceability**: links objective -> requirement -> test so nothing is missed or built without purpose.
- **UAT**: User Acceptance Testing - business users confirm the system meets the need.
- **KPI**: measurable indicator of performance. **SLA**: agreed service time target.
- **Bottleneck**: the workflow stage where work waits longest. **Stakeholder**: anyone affected by or influencing the solution.

## 14. Viva questions and answers
1. **What problem does InsightFlow solve?** It combines requirements management and SLA tracking so analysts can prove coverage and managers can see delays.
2. **Why scrypt?** It is a memory-hard, salted password hash available in Python's standard library; plain or fast hashes (MD5/SHA) are unsafe for passwords.
3. **What is a salt?** Random data added per password so equal passwords give different hashes and rainbow tables fail (`os.urandom(16)` in `hash_password`).
4. **How do you prevent SQL injection?** Parameterised queries with `?`; whitelist for sort column. There is a test that feeds `'; DROP TABLE...` as search text.
5. **What does `PRAGMA foreign_keys = ON` do?** SQLite ignores foreign keys by default; this makes it enforce them. Set in `db.connect`.
6. **Difference between CASCADE and SET NULL here?** Deleting a requirement cascades to its stories/tests; deleting an objective only nulls the reference.
7. **How is duplicate requirement ID prevented?** UNIQUE constraint plus pre-check in `validate_requirement` for a friendly message.
8. **How is RBAC enforced?** Permission sets per role, checked in the UI and again in `app.py`. (Honest limit: checks are in the UI layer, services themselves trust the caller.)
9. **How is SLA compliance defined?** On-time resolved / all resolved; open requests are excluded and shown as overdue/approaching separately.
10. **Why store status history?** Time-in-stage can't be known from the current status alone; history rows make bottleneck analysis real instead of fabricated.
11. **How do you find the bottleneck?** Average hours per visit for each open stage; highest average wins (`bottleneck_analysis`).
12. **What if no requests are resolved?** Compliance and average return None and the UI shows "n/a" - no divide-by-zero.
13. **What is traceability and how is it computed?** LEFT JOINs across objectives, requirements, stories, criteria and tests; gaps are NULLs.
14. **What is formula injection?** Text like `=HYPERLINK(...)` in a cell can execute in Excel; we prefix a quote (`sanitize_cell`).
15. **How does the CSV import handle bad rows?** Each row is validated; invalid/duplicate rows are skipped, counted and listed with line numbers.
16. **Why SQLite not MySQL?** No server to install for a beginner demo; same SQL ideas; production would use a server DB.
17. **How are timestamps handled?** Naive UTC strings, calendar-hour SLAs; documented limitation.
18. **How did you test?** 52 automated tests incl. known-value SLA cases, plus a stub-based UI smoke test; browser testing is manual.
19. **What would you improve?** Business hours, notifications, comments, database migrations, server-side sessions.
20. **How is this different from Jira?** It is a small teaching prototype showing the concepts (requirements, traceability, SLA) that tools like Jira implement at scale; it is not a replacement.
21. **Why do viewers still export?** Documented permission model: exports only read data; change in `PERMISSIONS` if policy differs.
22. **What is UAT and who performs it?** Business users run test cases against acceptance criteria before sign-off; here test cases are stored and linked to requirements.

## 15. Simple code explanations
```python
# auth.verify_password: split stored string into parameters, recompute scrypt with same salt, compare safely
dk = hashlib.scrypt(password.encode(), salt=salt, n=n, r=r, p=p, dklen=len(expected))
return hmac.compare_digest(dk, expected)
```
```python
# sla.classify: decides which bucket a request belongs to
if status is Resolved/Closed -> completed
elif now > due_at -> overdue
elif due_at - now <= window -> approaching
else on_track
```
