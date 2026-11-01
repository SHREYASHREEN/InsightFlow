# Data Model

Tables: users, settings, objectives, stakeholders, requirements, requirement_history, user_stories, acceptance_criteria,
uat_tests, doc_items, requests, status_history, schema_info. Foreign keys are enforced (`PRAGMA foreign_keys = ON`).

```
objectives 1---* requirements *---1 stakeholders (owner)      users 1---* requirements (analyst)
requirements 1---* user_stories
requirements 1---* acceptance_criteria  (optionally linked to one user story)
requirements 1---* uat_tests            (optionally linked to one acceptance criterion)
requirements 1---* requirement_history
requirements 1---* requests (optional link)   requests 1---* status_history
```
Deleting a requirement cascades to its stories, criteria, tests and history; linked requests are kept (link set to NULL).
Deleting an objective/stakeholder/user sets the reference on requirements to NULL.
Initialisation: `db.init_db()` uses `CREATE TABLE IF NOT EXISTS` and records `schema_info.version` (version 1).
Future schema changes would add numbered migration steps keyed on that version.
