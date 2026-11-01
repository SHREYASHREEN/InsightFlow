# InsightFlow - Business Requirements and Process Intelligence Platform
# InsightFlow – Business Requirements and Process Intelligence Platform

🚀 **[Live Application Demo](https://insightflow-ms8wwbsara5khcstl2zwd3.streamlit.app/)** | 💻 **[GitHub Source Code](https://github.com/SHREYASHREEN/InsightFlow)**

Explore the application using the demo credentials provided below.

A portfolio project that shows how a business analyst can document requirements, trace them to objectives and tests,
and track service requests against SLAs. **All data is fictional sample data** (a made-up company, "Northwind Service Desk").
It is a learning/portfolio prototype - not deployed, not production-ready, not for real confidential data.

**Stack:** Python, Streamlit, SQLite, pandas, Plotly, openpyxl. Password hashing uses `scrypt` from Python's standard library.

## Features
- Login / logout / registration (new accounts are Viewers), salted scrypt password hashes, session login state
- Role-based access: Admin, Business Analyst, Viewer (see table below)
- Requirements CRUD with validation, duplicate-ID prevention, search, filters, sorting and change history
- BA documentation: problem statement, objectives, scope, assumptions, constraints, risks, NFRs, process flow, change requests,
  stakeholders, user stories (As a / I want / So that), acceptance criteria (Given/When/Then or plain), UAT test cases
- Live traceability matrix (Objective -> Requirement -> Story -> Criterion -> UAT test) plus gap reports
- Request tracking with SLA deadlines, overdue / approaching / completed views, SLA compliance %, average resolution time,
  time-in-stage and bottleneck analysis computed from recorded status-change events
- Dashboard with KPI cards and Plotly charts
- CSV import (validated, duplicate detection, summary); CSV, Excel and Markdown exports with spreadsheet formula-injection protection

## Roles
| Capability | Admin | Business Analyst | Viewer |
|---|---|---|---|
| View dashboards, requirements, traceability, requests | yes | yes | yes |
| Export reports | yes | yes | yes |
| Create / edit requirements, documentation, requests, update status | yes | yes | no |
| Import CSV | yes | yes | no |
| Delete records | yes | no | no |
| Manage users and SLA settings | yes | no | no |

## Demo credentials (fictional, local demo only)
| Username | Password | Role |
|---|---|---|
| admin | Admin@12345 | Admin |
| analyst | Analyst@12345 | Business Analyst |
| viewer | Viewer@12345 | Viewer |

**Change these passwords (Administration -> Users) before using the app with any real information.**

## Windows setup (PowerShell in VS Code)
1. Install Python 3.10+ from python.org (tick "Add python.exe to PATH"). Check: `python --version`
2. Extract `InsightFlow.zip`, then in VS Code use **File -> Open Folder** and choose the `InsightFlow` folder.
3. Open the terminal: **Terminal -> New Terminal** (PowerShell). Confirm you are inside the folder: `Get-Location` should end with `InsightFlow`.
4. Create a virtual environment: `python -m venv .venv`
5. Activate it: `.\.venv\Scripts\Activate.ps1`
   (If PowerShell blocks scripts, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once, then try again.)
6. Install dependencies: `python -m pip install -r requirements.txt`
7. Create the database and sample data: `python scripts/seed_data.py`
8. Run the tests: `python -m pytest -q`   (or without pytest: `python -m unittest discover -s tests -t .`)
9. Start the app: `streamlit run app.py`
10. Open the address shown in the terminal (normally http://localhost:8501) and sign in as `analyst` / `Analyst@12345`.
11. Try: Requirements -> New requirement; Traceability (see gaps); Requests and SLA -> Update workflow; Reports -> download Excel.

To reset the sample data: `python scripts/seed_data.py --reset`. To stop the app press `Ctrl+C`.

## Troubleshooting
| Problem | Fix |
|---|---|
| `python` not recognised | Reinstall Python with "Add to PATH", or try `py -m venv .venv` |
| `ModuleNotFoundError` | The virtual environment is not active or step 6 was skipped. Run steps 5-6 again |
| `streamlit` not recognised | Use `python -m streamlit run app.py` |
| Port 8501 busy | `streamlit run app.py --server.port 8502` |
| `unable to open database file` / import errors | You are in the wrong folder. `cd` into the folder that contains `app.py` |
| "Invalid username or password" | Use the credentials above (case-sensitive). If you changed them and forgot, delete `data/insightflow.db` and run `python scripts/seed_data.py` |
| Empty dashboard | Run `python scripts/seed_data.py` |
| Sample CSV not found | Files are in `sample_data/` - upload from there on the Reports page |

## Project layout
```
app.py                    Streamlit entry point (login, navigation)
insightflow/
  config.py               statuses, priorities, SLA defaults
  db.py                   schema + connection (foreign keys ON)
  auth.py                 hashing, login, roles, permissions, user management
  requirements_service.py requirement validation + CRUD + search/filter/sort + history
  docs_service.py         objectives, stakeholders, stories, criteria, UAT tests, BA documents
  traceability.py         matrix + gap reports
  sla.py                  requests, status history, SLA metrics, bottlenecks
  kpis.py                 dashboard KPIs
  imports.py / exports.py CSV import; CSV/Excel/Markdown export + formula-injection protection
  seed.py                 fictional demo data
  ui.py                   Streamlit pages
scripts/seed_data.py      create DB + demo data
sample_data/              sample CSV files for import
tests/                    automated tests
docs/                     BRD, FRD, process flow, traceability example, user stories, UAT, KPI formulas, interview guide
```

## Testing status (honest summary)
Automated tests cover the database, authentication, permissions, validation, CRUD, duplicates, KPIs, SLA maths, traceability,
CSV import and CSV/Excel export. A mock-based smoke test runs every page function for every role. The visual layout in a real
browser was **not** verified by the author of this package - please click through the app once and report anything odd.
See `docs/KNOWN_LIMITATIONS.md`.
