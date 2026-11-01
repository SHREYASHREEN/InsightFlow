"""Fictional demo data: 'Northwind Service Desk' (all records are SAMPLE data)."""
import random
from datetime import timedelta
from . import auth, config, db, docs_service, requirements_service as rs, sla, timeutil

DEMO_USERS = [("admin", "Demo Admin", "Admin@12345", "Admin"),
              ("analyst", "Demo Analyst", "Analyst@12345", "Business Analyst"),
              ("viewer", "Demo Viewer", "Viewer@12345", "Viewer")]


def seed_users(conn):
    for username, name, pw, role in DEMO_USERS:
        if not conn.execute("SELECT 1 FROM users WHERE username=?", (username,)).fetchone():
            auth.create_user(conn, username, name, pw, role)


def seed_sample_data(conn, now=None, seed=42):
    """Idempotent: does nothing if requirements already exist. Request history is generated with a fixed seed
    but every status change is written to status_history so the metrics are computed from stored events."""
    if conn.execute("SELECT COUNT(*) FROM requirements").fetchone()[0] > 0:
        return False
    now = now or timeutil.now_utc()
    rnd = random.Random(seed)
    objs = [("OBJ-01", "Reduce average ticket resolution time", "Faster resolution improves employee productivity."),
            ("OBJ-02", "Improve SLA compliance to 90%", "Meet the agreed response and resolution targets."),
            ("OBJ-03", "Give managers visibility of service performance", "Dashboards and reports for decision making."),
            ("OBJ-04", "Introduce a self-service knowledge base", "Not yet linked to any requirement (a deliberate gap).")]
    oid = {}
    for code, t, d in objs:
        oid[code], _ = docs_service.add_objective(conn, code, t, d)
    sh = {}
    for name, role, dept, inf, inte in [("Asha Menon", "Service Desk Manager", "IT Support", "High", "High"),
                                        ("Rahul Verma", "Operations Head", "Operations", "High", "Medium"),
                                        ("Neha Kulkarni", "HR Business Partner", "HR", "Medium", "High"),
                                        ("Imran Sheikh", "Network Engineer", "IT Infrastructure", "Low", "Medium")]:
        sh[name], _ = docs_service.add_stakeholder(conn, name, role, dept, inf, inte)
    analyst = conn.execute("SELECT id FROM users WHERE username='analyst'").fetchone()
    aid = analyst["id"] if analyst else None
    reqs = [
        ("REQ-001", "Log a support request with mandatory fields", "Business", "Critical", "Approved", "OBJ-02", "Asha Menon"),
        ("REQ-002", "Auto-calculate SLA deadline from priority", "Functional", "Critical", "In Progress", "OBJ-02", "Asha Menon"),
        ("REQ-003", "Record every status change with a timestamp", "Functional", "High", "Completed", "OBJ-01", "Rahul Verma"),
        ("REQ-004", "Dashboard of open and overdue requests", "Functional", "High", "In Review", "OBJ-03", "Rahul Verma"),
        ("REQ-005", "Dashboard loads within 3 seconds for 10,000 requests", "Non-Functional", "Medium", "Proposed", "OBJ-03", "Rahul Verma"),
        ("REQ-006", "Export SLA summary to Excel", "Functional", "Medium", "Approved", "OBJ-03", "Neha Kulkarni"),
        ("REQ-007", "Notify owner when a request is close to its deadline", "Functional", "Medium", "Draft", "OBJ-02", "Asha Menon"),
        ("REQ-008", "Role-based access for analysts and viewers", "Non-Functional", "High", "Approved", None, "Imran Sheikh"),
    ]
    rpk = {}
    for rid, title, typ, pri, st, obj, owner in reqs:
        rpk[rid], errs = rs.create_requirement(conn, dict(
            req_id=rid, title=title, description="SAMPLE: " + title, req_type=typ, priority=pri, status=st,
            objective_id=oid.get(obj), owner_id=sh[owner], analyst_id=aid,
            due_date=timeutil.to_str(now + timedelta(days=30))[:10], dependencies="REQ-001" if rid == "REQ-002" else ""),
            user="seed", created_at=timeutil.to_str(now - timedelta(days=20)))
    stories = [("US-001", "REQ-001", "service desk agent", "to log a request with category and priority", "every ticket can be triaged correctly"),
               ("US-002", "REQ-002", "service desk manager", "the SLA deadline to be calculated automatically", "I do not have to compute it by hand"),
               ("US-003", "REQ-004", "operations head", "to see overdue requests by owner", "I can rebalance the workload"),
               ("US-004", "REQ-006", "HR business partner", "to download the SLA summary as Excel", "I can share it in the monthly review")]
    sid = {}
    for story_id, rid, a, w, s in stories:
        sid[story_id], _ = docs_service.add_story(conn, story_id, rpk[rid], a, w, s)
    ac = {}
    ac["a"], _ = docs_service.add_criterion(conn, rpk["REQ-001"], "a logged-in agent", "they submit a request without a title",
                                             "the form shows 'Title is required' and nothing is saved", story_id=sid["US-001"])
    ac["b"], _ = docs_service.add_criterion(conn, rpk["REQ-002"], "a High priority request is created at 09:00",
                                             "the request is saved", "its due time is 17:00 the same day", story_id=sid["US-002"])
    ac["c"], _ = docs_service.add_criterion(conn, rpk["REQ-003"], description="Each status change creates one history row with old status, new status and time.")
    ac["d"], _ = docs_service.add_criterion(conn, rpk["REQ-004"], "five requests are past their due time",
                                             "the manager opens the dashboard", "the Overdue KPI shows 5", story_id=sid["US-003"])
    docs_service.add_uat_test(conn, "UAT-001", "Reject request without title", rpk["REQ-001"],
                              "1. Open New Request. 2. Leave title empty. 3. Submit.", "Error message shown", "Passed", ac["a"])
    docs_service.add_uat_test(conn, "UAT-002", "SLA deadline for High priority", rpk["REQ-002"],
                              "1. Create a High request. 2. Read the due time.", "Due = created + 8 hours", "Not Run", ac["b"])
    docs_service.add_uat_test(conn, "UAT-003", "History row on status change", rpk["REQ-003"],
                              "1. Change a status. 2. Open history.", "One new row", "Passed", ac["c"])
    docs_service.add_uat_test(conn, "UAT-004", "Overdue KPI matches table", rpk["REQ-004"],
                              "1. Open dashboard. 2. Compare KPI and table.", "Counts match", "Failed", ac["d"])
    for sec, title, content in [
        ("Problem Statement", "Slow and untracked support requests", "SAMPLE: Northwind's service desk has no consistent way to measure SLA compliance or find where tickets wait."),
        ("Business Objective", "Improve SLA compliance", "SAMPLE: Reach 90% on-time resolution within 6 months."),
        ("Project Scope", "In scope", "SAMPLE: request logging, SLA tracking, dashboards, exports. Out of scope: email integration, chatbots."),
        ("Assumption", "Calendar-hour SLAs", "SAMPLE: SLAs run 24x7 and do not pause on weekends."),
        ("Constraint", "Single-user SQLite", "SAMPLE: The prototype uses SQLite and is not designed for heavy concurrent use."),
        ("Risk", "Poor data quality", "SAMPLE: Agents may forget to update statuses, which distorts stage durations."),
        ("Dependency", "Stakeholder availability", "SAMPLE: Managers must be available for UAT."),
        ("Non-Functional Requirement", "Security", "SAMPLE: Passwords stored as salted hashes; access limited by role."),
        ("Process Flow", "Request lifecycle", "New -> Assigned -> In Progress -> (Pending Info) -> Resolved -> Closed"),
        ("Change Request", "CR-001 add priority 'Critical'", "SAMPLE: Requested by Operations; approved; impacts REQ-002."),
    ]:
        docs_service.add_doc_item(conn, sec, title, content)
    # Requests with real event histories (fixed seed => reproducible). Dates are relative to `now`.
    owners = ["Asha Menon", "Imran Sheikh", "Neha Kulkarni", "Rahul Verma"]
    reqpks = list(rpk.values())
    for i in range(1, 41):
        created = now - timedelta(hours=rnd.randint(6, 24 * 28))
        pri = rnd.choice(config.REQ_PRIORITIES)
        owner = rnd.choice(owners)
        pk, _ = sla.create_request(conn, dict(
            request_id=f"RQ-{i:04d}", title=f"SAMPLE request {i}", description="Fictional sample ticket",
            category=rnd.choice(config.REQUEST_CATEGORIES), priority=pri, requester=f"Employee {rnd.randint(1, 25)}",
            owner=owner, requirement_id=rnd.choice(reqpks) if rnd.random() < 0.4 else None),
            user="seed", created_at=timeutil.to_str(created))
        t = created
        path = [("In Progress", rnd.uniform(0.5, 6))]
        if rnd.random() < 0.3:
            path.append(("Pending Info", rnd.uniform(2, 30)))
            path.append(("In Progress", rnd.uniform(0.5, 8)))
        if rnd.random() < 0.8:
            path.append(("Resolved", None))
        for status, gap in path:
            t = t + timedelta(hours=gap if gap is not None else rnd.uniform(0.2, 4))
            if t >= now:
                break
            sla.change_status(conn, pk, status, user="seed", at=timeutil.to_str(t.replace(microsecond=0)))
    return True


def reset_demo(conn):
    for t in ["status_history", "requests", "uat_tests", "acceptance_criteria", "user_stories",
              "requirement_history", "requirements", "doc_items", "stakeholders", "objectives"]:
        conn.execute(f"DELETE FROM {t}")
    conn.commit()
