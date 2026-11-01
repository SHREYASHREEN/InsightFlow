"""Streamlit user interface. All business rules live in the other modules; this file only draws pages."""
import html
from datetime import date, timedelta

import pandas as pd
import plotly.express as px
import streamlit as st

from . import auth, config, docs_service, exports, imports, kpis, requirements_service as rs, sla, traceability

NAVY, TEAL, AMBER, RED, GREY = "#16324f", "#1b8a8f", "#e0a030", "#c0392b", "#6b7785"
STATUS_COLORS = {"Draft": "#8d99a6", "Proposed": "#5b7fa6", "Approved": "#1b8a8f", "In Progress": "#3a6fd8",
                 "In Review": "#e0a030", "Completed": "#2e8b57", "Rejected": "#c0392b",
                 "New": "#8d99a6", "Assigned": "#5b7fa6", "Pending Info": "#e0a030", "Resolved": "#2e8b57", "Closed": "#16324f"}
CSS = f"""
<style>
.block-container {{padding-top: 1.6rem; max-width: 1250px;}}
h1, h2, h3 {{color: {NAVY}; font-family: 'Segoe UI', sans-serif;}}
.kpi {{background:#fff;border:1px solid #dfe5ec;border-left:5px solid {TEAL};border-radius:8px;padding:12px 16px;}}
.kpi .v {{font-size:1.9rem;font-weight:700;color:{NAVY};line-height:1.1;}}
.kpi .l {{font-size:.78rem;color:{GREY};text-transform:uppercase;letter-spacing:.04em;}}
.kpi.warn {{border-left-color:{RED};}} .kpi.amber {{border-left-color:{AMBER};}}
.badge {{display:inline-block;padding:2px 10px;border-radius:12px;color:#fff;font-size:.78rem;font-weight:600;}}
[data-testid="stSidebar"] {{background:{NAVY};}}
[data-testid="stSidebar"] * {{color:#eaf1f7 !important;}}
</style>"""


def inject_css():
    st.markdown(CSS, unsafe_allow_html=True)


def kpi_card(label, value, kind=""):
    st.markdown(f'<div class="kpi {kind}"><div class="l">{html.escape(str(label))}</div>'
                f'<div class="v">{html.escape(str(value))}</div></div>', unsafe_allow_html=True)


def badge(text):
    color = STATUS_COLORS.get(text, GREY)
    return f'<span class="badge" style="background:{color}">{html.escape(str(text))}</span>'


def show_errors(errors):
    for e in errors:
        st.error(e)


def empty_state(message):
    st.info(message)


def fmt(v, suffix=""):
    return "n/a" if v is None else f"{v}{suffix}"


def require(user, permission):
    if not auth.has_permission(user["role"], permission):
        st.warning("Your role does not have permission to do this.")
        return False
    return True


# ------------------------------------------------------------------ login
def login_page(conn):
    inject_css()
    st.title("InsightFlow")
    st.caption("Business Requirements and Process Intelligence Platform - portfolio demo (sample data only)")
    tab_login, tab_register = st.tabs(["Sign in", "Register (Viewer access)"])
    with tab_login:
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            go = st.form_submit_button("Sign in", type="primary")
        if go:
            user, msg = auth.authenticate(conn, username, password)
            if user:
                st.session_state["user"] = user
                st.rerun()
            else:
                st.error(msg)
    with tab_register:
        with st.form("register_form"):
            u = st.text_input("Choose a username")
            n = st.text_input("Full name")
            p = st.text_input("Choose a password (8+ characters, letters and digits)", type="password")
            reg = st.form_submit_button("Create account")
        if reg:
            _, errors = auth.create_user(conn, u, n, p, "Viewer")
            if errors:
                show_errors(errors)
            else:
                st.success("Account created with Viewer access. You can sign in now.")


# --------------------------------------------------------------- overview
def page_overview(conn, user):
    st.header("Overview")
    d = kpis.overview(conn)
    c = st.columns(4)
    with c[0]: kpi_card("Total requirements", d["total_requirements"])
    with c[1]: kpi_card("Open requests", d["open_requests"])
    with c[2]: kpi_card("Overdue requests", d["overdue_requests"], "warn" if d["overdue_requests"] else "")
    with c[3]: kpi_card("SLA compliance", fmt(d["sla_compliance_pct"], "%"))
    c = st.columns(4)
    with c[0]: kpi_card("Avg resolution (hours)", fmt(d["avg_resolution_hours"]))
    with c[1]: kpi_card("Due soon", d["approaching_deadline"], "amber" if d["approaching_deadline"] else "")
    with c[2]: kpi_card("Reqs without acceptance criteria", d["missing_acceptance_criteria"], "amber" if d["missing_acceptance_criteria"] else "")
    with c[3]: kpi_card("Reqs without UAT tests", d["missing_uat_tests"], "amber" if d["missing_uat_tests"] else "")
    st.write("")
    left, right = st.columns(2)
    with left:
        st.subheader("Requirements by status and priority")
        df = pd.DataFrame(d["by_priority_status"])
        if df.empty:
            empty_state("No requirements yet.")
        else:
            fig = px.bar(df, x="status", y="n", color="priority", labels={"n": "Requirements", "status": "Status"},
                         category_orders={"status": config.REQ_STATUSES, "priority": config.REQ_PRIORITIES},
                         color_discrete_sequence=[RED, AMBER, TEAL, GREY])
            st.plotly_chart(fig, use_container_width=True)
    with right:
        st.subheader("Requests by category")
        cat = kpis.request_by_category(conn)
        if not cat:
            empty_state("No requests yet.")
        else:
            fig = px.pie(names=list(cat.keys()), values=list(cat.values()), hole=0.45,
                         color_discrete_sequence=px.colors.sequential.Teal_r)
            st.plotly_chart(fig, use_container_width=True)
    left, right = st.columns(2)
    with left:
        st.subheader("Overdue requests by owner")
        ov = sla.overdue_by_owner(conn)
        if not ov:
            empty_state("No overdue requests.")
        else:
            fig = px.bar(x=list(ov.keys()), y=list(ov.values()), labels={"x": "Owner", "y": "Overdue"},
                         color_discrete_sequence=[RED])
            st.plotly_chart(fig, use_container_width=True)
    with right:
        st.subheader("SLA compliance trend (by month resolved)")
        tr = sla.compliance_trend(conn)
        if len(tr) < 2:
            empty_state("At least two months of resolved requests are needed for a trend.")
        else:
            fig = px.line(pd.DataFrame(tr), x="month", y="compliance_pct", markers=True,
                          labels={"compliance_pct": "Compliance %", "month": "Month"}, color_discrete_sequence=[TEAL])
            fig.update_yaxes(range=[0, 100])
            st.plotly_chart(fig, use_container_width=True)


# ----------------------------------------------------------- requirements
def _lookup(conn):
    objs = {o["id"]: f"{o['code']} - {o['title']}" for o in docs_service.list_objectives(conn)}
    owners = {s["id"]: s["name"] for s in docs_service.list_stakeholders(conn)}
    analysts = {u["id"]: u["full_name"] for u in auth.list_users(conn) if u["role"] != "Viewer"}
    return objs, owners, analysts


def requirement_form(conn, user, existing=None):
    objs, owners, analysts = _lookup(conn)
    e = existing or {}
    key = f"reqform_{e.get('id', 'new')}"
    with st.form(key):
        c = st.columns(2)
        req_id = c[0].text_input("Requirement ID", value=e.get("req_id") or rs.next_req_id(conn))
        title = c[1].text_input("Title", value=e.get("title", ""))
        desc = st.text_area("Description", value=e.get("description", ""))
        c = st.columns(3)
        req_type = c[0].selectbox("Type", config.REQ_TYPES, index=config.REQ_TYPES.index(e["req_type"]) if e.get("req_type") in config.REQ_TYPES else 1)
        priority = c[1].selectbox("Priority", config.REQ_PRIORITIES, index=config.REQ_PRIORITIES.index(e["priority"]) if e.get("priority") in config.REQ_PRIORITIES else 2)
        status = c[2].selectbox("Status", config.REQ_STATUSES, index=config.REQ_STATUSES.index(e["status"]) if e.get("status") in config.REQ_STATUSES else 0)
        c = st.columns(3)
        obj_opts = [None] + list(objs.keys())
        owner_opts = [None] + list(owners.keys())
        an_opts = [None] + list(analysts.keys())
        objective = c[0].selectbox("Business objective", obj_opts, index=obj_opts.index(e.get("objective_id")) if e.get("objective_id") in obj_opts else 0, format_func=lambda k: "(none)" if k is None else objs[k])
        owner = c[1].selectbox("Stakeholder / owner", owner_opts, index=owner_opts.index(e.get("owner_id")) if e.get("owner_id") in owner_opts else 0, format_func=lambda k: "(none)" if k is None else owners[k])
        analyst = c[2].selectbox("Assigned analyst", an_opts, index=an_opts.index(e.get("analyst_id")) if e.get("analyst_id") in an_opts else 0, format_func=lambda k: "(none)" if k is None else analysts[k])
        c = st.columns(2)
        has_due = c[0].checkbox("Has due date", value=bool(e.get("due_date")))
        due = c[1].date_input("Due date", value=pd.to_datetime(e["due_date"]).date() if e.get("due_date") else date.today() + timedelta(days=30))
        deps = st.text_input("Dependencies (comma-separated requirement IDs)", value=e.get("dependencies", ""))
        submitted = st.form_submit_button("Save changes" if existing else "Create requirement", type="primary")
    if submitted:
        data = dict(req_id=req_id, title=title, description=desc, req_type=req_type, priority=priority, status=status,
                    objective_id=objective, owner_id=owner, analyst_id=analyst,
                    due_date=str(due) if has_due else None, dependencies=deps)
        if existing:
            errors = rs.update_requirement(conn, existing["id"], data, user["username"])
        else:
            _, errors = rs.create_requirement(conn, data, user["username"])
        if errors:
            show_errors(errors)
        else:
            st.success("Requirement saved.")
            st.rerun()


def page_requirements(conn, user):
    st.header("Requirements")
    tab_list, tab_new, tab_edit = st.tabs(["Browse", "New requirement", "Edit / delete"])
    with tab_list:
        objs, owners, _ = _lookup(conn)
        c = st.columns([2, 1, 1, 1])
        search = c[0].text_input("Search ID, title or description")
        pri = c[1].multiselect("Priority", config.REQ_PRIORITIES)
        stat = c[2].multiselect("Status", config.REQ_STATUSES)
        owner = c[3].selectbox("Owner", [None] + list(owners.keys()), format_func=lambda k: "All" if k is None else owners[k])
        c = st.columns([1, 1, 1, 1])
        use_dates = c[0].checkbox("Filter by created date")
        d_from = c[1].date_input("From", value=date.today() - timedelta(days=90), disabled=not use_dates)
        d_to = c[2].date_input("To", value=date.today(), disabled=not use_dates)
        sort_by = c[3].selectbox("Sort by", list(rs.SORT_COLUMNS.keys()))
        desc_order = st.checkbox("Descending")
        rows = rs.list_requirements(conn, search, pri, stat, owner, d_from if use_dates else None,
                                    d_to if use_dates else None, sort_by, desc_order)
        if not rows:
            empty_state("No requirements match the filters.")
        else:
            df = pd.DataFrame(rows)[["req_id", "title", "req_type", "priority", "status", "objective", "owner", "analyst", "due_date"]]
            df.columns = ["ID", "Title", "Type", "Priority", "Status", "Objective", "Owner", "Analyst", "Due date"]
            st.dataframe(df, use_container_width=True, hide_index=True)
            st.caption(f"{len(rows)} requirement(s). Status legend: " + " ".join(badge(s) for s in config.REQ_STATUSES), unsafe_allow_html=True)
    with tab_new:
        if require(user, "requirement.write"):
            requirement_form(conn, user)
    with tab_edit:
        if not auth.has_permission(user["role"], "requirement.write"):
            st.warning("Your role can view requirements but not edit them.")
            return
        rows = rs.list_requirements(conn)
        if not rows:
            empty_state("No requirements to edit.")
            return
        pk = st.selectbox("Choose a requirement", [r["id"] for r in rows],
                          format_func=lambda i: next(f"{r['req_id']} - {r['title']}" for r in rows if r["id"] == i))
        requirement_form(conn, user, rs.get_requirement(conn, pk))
        with st.expander("Change history"):
            hist = rs.requirement_history(conn, pk)
            if hist:
                st.dataframe(pd.DataFrame(hist), use_container_width=True, hide_index=True)
            else:
                empty_state("No history yet.")
        if auth.has_permission(user["role"], "requirement.delete"):
            st.subheader("Delete")
            ok = st.checkbox("I understand this also deletes linked stories, criteria, tests and history", key=f"del_ok_{pk}")
            if st.button("Delete requirement", disabled=not ok):
                rs.delete_requirement(conn, pk)
                st.success("Requirement deleted.")
                st.rerun()
        else:
            st.caption("Only an Admin can delete requirements.")


# ------------------------------------------------------- documentation
def page_documentation(conn, user):
    st.header("Business Analysis Documentation")
    can_write = auth.has_permission(user["role"], "docs.write")
    can_delete = auth.has_permission(user["role"], "docs.delete")
    tabs = st.tabs(["BA document", "Objectives", "Stakeholders", "User stories", "Acceptance criteria", "UAT tests"])
    with tabs[0]:
        for section in config.DOC_SECTIONS:
            items = docs_service.list_doc_items(conn, section)
            with st.expander(f"{section} ({len(items)})"):
                for it in items:
                    st.markdown(f"**{it['title']}**")
                    st.write(it["content"])
                    if can_delete and st.button("Delete", key=f"deldoc_{it['id']}"):
                        docs_service.delete_doc_item(conn, it["id"]); st.rerun()
                if not items:
                    empty_state("Nothing documented yet.")
        if can_write:
            with st.form("doc_form"):
                section = st.selectbox("Section", config.DOC_SECTIONS)
                title = st.text_input("Title")
                content = st.text_area("Content")
                if st.form_submit_button("Add item", type="primary"):
                    _, errs = docs_service.add_doc_item(conn, section, title, content)
                    show_errors(errs) if errs else (st.success("Added."), st.rerun())
    with tabs[1]:
        objs = docs_service.list_objectives(conn)
        st.dataframe(pd.DataFrame(objs, columns=["code", "title", "description"]) if objs else pd.DataFrame(columns=["code", "title", "description"]), use_container_width=True, hide_index=True)
        if can_write:
            with st.form("obj_form"):
                c = st.columns([1, 3])
                code = c[0].text_input("Code (OBJ-01)")
                title = c[1].text_input("Title")
                desc = st.text_area("Description")
                if st.form_submit_button("Add objective"):
                    _, errs = docs_service.add_objective(conn, code, title, desc)
                    show_errors(errs) if errs else (st.success("Added."), st.rerun())
        if can_delete and objs:
            pick = st.selectbox("Delete objective", [o["id"] for o in objs], format_func=lambda i: next(o["code"] for o in objs if o["id"] == i))
            if st.button("Delete selected objective"):
                docs_service.delete_objective(conn, pick); st.rerun()
    with tabs[2]:
        sh = docs_service.list_stakeholders(conn)
        st.dataframe(pd.DataFrame(sh) if sh else pd.DataFrame(columns=["name", "role", "department"]), use_container_width=True, hide_index=True)
        if can_write:
            with st.form("sh_form"):
                c = st.columns(3)
                name, role, dept = c[0].text_input("Name"), c[1].text_input("Role"), c[2].text_input("Department")
                c = st.columns(2)
                inf = c[0].selectbox("Influence", ["High", "Medium", "Low"], index=1)
                inte = c[1].selectbox("Interest", ["High", "Medium", "Low"], index=1)
                if st.form_submit_button("Add stakeholder"):
                    _, errs = docs_service.add_stakeholder(conn, name, role, dept, inf, inte)
                    show_errors(errs) if errs else (st.success("Added."), st.rerun())
        if can_delete and sh:
            pick = st.selectbox("Delete stakeholder", [s["id"] for s in sh], format_func=lambda i: next(s["name"] for s in sh if s["id"] == i))
            if st.button("Delete selected stakeholder"):
                docs_service.delete_stakeholder(conn, pick); st.rerun()
    reqs = rs.list_requirements(conn)
    req_label = lambda i: next(f"{r['req_id']} - {r['title']}" for r in reqs if r["id"] == i)
    with tabs[3]:
        st.caption("Format: As a [user], I want [capability], so that [business value].")
        stories = docs_service.list_stories(conn)
        if stories:
            st.dataframe(pd.DataFrame(stories)[["story_id", "req_id", "text"]], use_container_width=True, hide_index=True)
        else:
            empty_state("No user stories yet.")
        if can_write and reqs:
            with st.form("story_form"):
                c = st.columns([1, 3])
                sid = c[0].text_input("Story ID (US-001)")
                rq = c[1].selectbox("Requirement", [r["id"] for r in reqs], format_func=req_label)
                a, w, s = st.text_input("As a"), st.text_input("I want"), st.text_input("So that")
                if st.form_submit_button("Add story"):
                    _, errs = docs_service.add_story(conn, sid, rq, a, w, s)
                    show_errors(errs) if errs else (st.success("Added."), st.rerun())
        if can_delete and stories:
            pick = st.selectbox("Delete story", [s["id"] for s in stories], format_func=lambda i: next(s["story_id"] for s in stories if s["id"] == i))
            if st.button("Delete selected story"):
                docs_service.delete_story(conn, pick); st.rerun()
    with tabs[4]:
        st.caption("Use Given/When/Then, or leave those empty and write a plain description.")
        crit = docs_service.list_criteria(conn)
        if crit:
            st.dataframe(pd.DataFrame(crit)[["id", "req_id", "text"]], use_container_width=True, hide_index=True)
        else:
            empty_state("No acceptance criteria yet.")
        if can_write and reqs:
            with st.form("crit_form"):
                rq = st.selectbox("Requirement", [r["id"] for r in reqs], format_func=req_label)
                g, w, t = st.text_input("Given"), st.text_input("When"), st.text_input("Then")
                d = st.text_area("Or plain description")
                if st.form_submit_button("Add criterion"):
                    _, errs = docs_service.add_criterion(conn, rq, g, w, t, d)
                    show_errors(errs) if errs else (st.success("Added."), st.rerun())
        if can_delete and crit:
            pick = st.selectbox("Delete criterion", [c["id"] for c in crit])
            if st.button("Delete selected criterion"):
                docs_service.delete_criterion(conn, pick); st.rerun()
    with tabs[5]:
        tests = docs_service.list_uat_tests(conn)
        if tests:
            st.dataframe(pd.DataFrame(tests)[["test_id", "req_id", "title", "status", "expected_result"]], use_container_width=True, hide_index=True)
        else:
            empty_state("No UAT test cases yet.")
        if can_write and tests:
            c = st.columns(3)
            pick = c[0].selectbox("Update test result", [t["id"] for t in tests], format_func=lambda i: next(t["test_id"] for t in tests if t["id"] == i))
            new = c[1].selectbox("New status", config.UAT_STATUSES)
            if c[2].button("Update status"):
                docs_service.set_uat_status(conn, pick, new); st.rerun()
        if can_write and reqs:
            with st.form("uat_form"):
                c = st.columns([1, 3])
                tid = c[0].text_input("Test ID (UAT-001)")
                title = c[1].text_input("Title")
                rq = st.selectbox("Requirement", [r["id"] for r in reqs], format_func=req_label)
                steps, exp = st.text_area("Steps"), st.text_input("Expected result")
                if st.form_submit_button("Add test case"):
                    _, errs = docs_service.add_uat_test(conn, tid, title, rq, steps, exp)
                    show_errors(errs) if errs else (st.success("Added."), st.rerun())
        if can_delete and tests:
            pick = st.selectbox("Delete test", [t["id"] for t in tests], format_func=lambda i: next(t["test_id"] for t in tests if t["id"] == i))
            if st.button("Delete selected test"):
                docs_service.delete_uat_test(conn, pick); st.rerun()


# ----------------------------------------------------------- traceability
def page_traceability(conn, user):
    st.header("Traceability Matrix")
    st.caption("Objective -> Requirement -> User story -> Acceptance criterion -> UAT test (live from the database)")
    cov = traceability.coverage_summary(conn)
    c = st.columns(4)
    with c[0]: kpi_card("Requirements", cov["total_requirements"])
    with c[1]: kpi_card("Acceptance criteria coverage", fmt(cov["acceptance_criteria_coverage_pct"], "%"))
    with c[2]: kpi_card("UAT coverage", fmt(cov["uat_coverage_pct"], "%"))
    with c[3]: kpi_card("Objectives without requirements", cov["objectives_without_requirements"], "amber" if cov["objectives_without_requirements"] else "")
    matrix = traceability.build_matrix(conn)
    if not matrix:
        empty_state("No requirements to trace yet.")
    else:
        df = pd.DataFrame(matrix).drop(columns=["criterion_id"]).fillna("-")
        df.columns = ["Objective", "Requirement", "Title", "Req status", "Story", "Acceptance criterion", "UAT test", "UAT status"]
        st.dataframe(df, use_container_width=True, hide_index=True)
    st.subheader("Gaps")
    labels = {"no_acceptance_criteria": "Requirements without acceptance criteria",
              "no_uat_tests": "Requirements without linked UAT test cases",
              "no_user_story": "Requirements without a user story",
              "objectives_without_requirements": "Objectives with no requirements",
              "requirements_without_objective": "Requirements not linked to an objective",
              "unapproved_or_incomplete": "Unapproved or incomplete requirements (Draft/Proposed)"}
    for key, items in traceability.gap_report(conn).items():
        with st.expander(f"{labels[key]} ({len(items)})"):
            if items:
                st.dataframe(pd.DataFrame(items), use_container_width=True, hide_index=True)
            else:
                st.success("No gaps found.")


# --------------------------------------------------------------- requests
def page_requests(conn, user):
    st.header("Requests and SLA")
    can_write = auth.has_permission(user["role"], "request.write")
    tabs = st.tabs(["Dashboard", "All requests", "New request", "Update workflow"])
    with tabs[0]:
        s = sla.sla_summary(conn)
        c = st.columns(4)
        with c[0]: kpi_card("Open", s["open_requests"])
        with c[1]: kpi_card("Overdue", s["overdue_requests"], "warn" if s["overdue_requests"] else "")
        with c[2]: kpi_card("Due soon", s["approaching_deadline"], "amber" if s["approaching_deadline"] else "")
        with c[3]: kpi_card("SLA compliance", fmt(s["sla_compliance_pct"], "%"))
        b = sla.request_buckets(conn)
        for name, key in [("Overdue", "overdue"), ("Approaching deadline", "approaching"), ("Completed", "completed")]:
            with st.expander(f"{name} ({len(b[key])})", expanded=(key == "overdue")):
                if b[key]:
                    st.dataframe(pd.DataFrame(b[key])[["request_id", "title", "priority", "owner", "status", "due_at", "resolved_at"]], use_container_width=True, hide_index=True)
                else:
                    empty_state("None.")
        st.subheader("Time spent in workflow stages")
        bn = sla.bottleneck_analysis(conn)
        if not bn["stages"]:
            empty_state("No status history recorded yet.")
        else:
            df = pd.DataFrame(bn["stages"])
            fig = px.bar(df, x="stage", y="avg_hours", labels={"avg_hours": "Average hours in stage", "stage": "Stage"}, color_discrete_sequence=[TEAL])
            st.plotly_chart(fig, use_container_width=True)
            st.write(f"**Bottleneck stage (highest average time):** {bn['bottleneck']}")
            st.caption("Computed from recorded status-change events. Open requests count time up to now.")
    with tabs[1]:
        rows = sla.list_requests(conn)
        if rows:
            st.dataframe(pd.DataFrame(rows)[["request_id", "title", "category", "priority", "requester", "owner", "status", "created_at", "due_at", "resolved_at"]], use_container_width=True, hide_index=True)
        else:
            empty_state("No requests yet.")
    with tabs[2]:
        if can_write:
            reqs = rs.list_requirements(conn)
            with st.form("req_new"):
                title = st.text_input("Title")
                desc = st.text_area("Description")
                c = st.columns(3)
                cat = c[0].selectbox("Category", config.REQUEST_CATEGORIES)
                pri = c[1].selectbox("Priority", config.REQ_PRIORITIES, index=2)
                requester = c[2].text_input("Requester")
                owner = st.text_input("Assigned owner (optional)")
                link = st.selectbox("Linked requirement", [None] + [r["id"] for r in reqs], format_func=lambda i: "(none)" if i is None else next(r["req_id"] for r in reqs if r["id"] == i))
                st.caption(f"SLA deadline = creation time + {sla.sla_hours_for(conn, pri)} hours for {pri} priority.")
                if st.form_submit_button("Create request", type="primary"):
                    _, errs = sla.create_request(conn, dict(title=title, description=desc, category=cat, priority=pri,
                                                            requester=requester, owner=owner, requirement_id=link), user["username"])
                    show_errors(errs) if errs else (st.success("Request created."), st.rerun())
        else:
            st.warning("Your role cannot create requests.")
    with tabs[3]:
        rows = sla.list_requests(conn)
        if not can_write:
            st.warning("Your role cannot update workflow status.")
        elif not rows:
            empty_state("No requests yet.")
        else:
            pk = st.selectbox("Request", [r["id"] for r in rows], format_func=lambda i: next(f"{r['request_id']} - {r['title']} [{r['status']}]" for r in rows if r["id"] == i))
            c = st.columns(2)
            new = c[0].selectbox("Move to status", config.REQUEST_STATUSES)
            if c[1].button("Update status", type="primary"):
                errs = sla.change_status(conn, pk, new, user["username"])
                show_errors(errs) if errs else (st.success("Status updated."), st.rerun())
            hist = [dict(r) for r in conn.execute("SELECT from_status, to_status, changed_at, changed_by FROM status_history WHERE request_pk=? ORDER BY changed_at, id", (pk,))]
            st.dataframe(pd.DataFrame(hist), use_container_width=True, hide_index=True)
            if auth.has_permission(user["role"], "request.delete"):
                ok = st.checkbox("Confirm delete of this request", key=f"rqdel_{pk}")
                if st.button("Delete request", disabled=not ok):
                    sla.delete_request(conn, pk); st.rerun()


# ----------------------------------------------------------------- reports
def page_reports(conn, user):
    st.header("Reports, Import and Export")
    if not auth.has_permission(user["role"], "export"):
        st.warning("Your role cannot export reports.")
    else:
        st.subheader("Downloads")
        req_df = exports.requirements_df(conn)
        c = st.columns(3)
        c[0].download_button("Requirements (CSV)", exports.df_to_csv_bytes(req_df), "requirements.csv", "text/csv")
        c[1].download_button("Requirements report (Markdown)", exports.requirements_markdown(conn), "requirements_report.md", "text/markdown")
        c[2].download_button("Traceability report (Markdown)", exports.traceability_markdown(conn), "traceability_report.md", "text/markdown")
        c = st.columns(3)
        c[0].download_button("SLA summary (Markdown)", exports.sla_markdown(conn), "sla_summary.md", "text/markdown")
        c[1].download_button("Traceability matrix (CSV)", exports.df_to_csv_bytes(exports.traceability_df(conn)), "traceability.csv", "text/csv")
        c[2].download_button("SLA summary (CSV)", exports.df_to_csv_bytes(exports.sla_summary_df(conn)), "sla_summary.csv", "text/csv")
        xlsx = exports.dfs_to_excel_bytes({"Requirements": req_df, "Requests": exports.requests_df(conn),
                                           "Traceability": exports.traceability_df(conn), "SLA summary": exports.sla_summary_df(conn)})
        st.download_button("Full workbook (Excel)", xlsx, "insightflow_report.xlsx",
                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", type="primary")
    st.subheader("Import requirements from CSV")
    if not auth.has_permission(user["role"], "import"):
        st.caption("Your role cannot import data.")
        return
    st.caption("Required columns: " + ", ".join(imports.REQUIRED) + ". Optional: " + ", ".join(imports.OPTIONAL))
    up = st.file_uploader("Choose a CSV file", type=["csv"])
    if up is not None and st.button("Run import", type="primary"):
        res = imports.import_requirements_csv(conn, up.getvalue(), user["username"])
        if res["imported"]:
            st.success(f"Imported {res['imported']} of {res['rows']} rows.")
        st.write(f"Duplicates skipped: {res['duplicates']} | Invalid rows: {res['invalid']}")
        for e in res["errors"]:
            st.warning(e)


# ------------------------------------------------------------------- admin
def page_admin(conn, user):
    st.header("Administration")
    if not require(user, "user.manage"):
        return
    tab_users, tab_settings = st.tabs(["Users", "Settings"])
    with tab_users:
        users = auth.list_users(conn)
        st.dataframe(pd.DataFrame(users), use_container_width=True, hide_index=True)
        with st.form("new_user"):
            c = st.columns(4)
            u, n, p = c[0].text_input("Username"), c[1].text_input("Full name"), c[2].text_input("Password", type="password")
            role = c[3].selectbox("Role", config.ROLES)
            if st.form_submit_button("Create user"):
                _, errs = auth.create_user(conn, u, n, p, role)
                show_errors(errs) if errs else (st.success("User created."), st.rerun())
        if not users:
            return
        st.subheader("Edit a user")
        pick = st.selectbox("User", [x["id"] for x in users], format_func=lambda i: next(x["username"] for x in users if x["id"] == i))
        target = next(x for x in users if x["id"] == pick)
        c = st.columns(3)
        new_role = c[0].selectbox("Role", config.ROLES, index=config.ROLES.index(target["role"]))
        active = c[1].checkbox("Active", value=bool(target["active"]))
        new_pw = c[2].text_input("New password (optional)", type="password")
        if st.button("Save user changes"):
            if pick == user["id"] and (new_role != "Admin" or not active):
                st.error("You cannot remove your own Admin access or disable your own account.")
            else:
                auth.set_user_role(conn, pick, new_role)
                auth.set_user_active(conn, pick, active)
                errs = auth.reset_password(conn, pick, new_pw) if new_pw else []
                show_errors(errs) if errs else (st.success("User updated."), st.rerun())
        if pick != user["id"]:
            ok = st.checkbox("Confirm delete user", key=f"udel_{pick}")
            if st.button("Delete user", disabled=not ok):
                auth.delete_user(conn, pick); st.rerun()
    with tab_settings:
        if not require(user, "settings.manage"):
            return
        st.caption("SLA targets in calendar hours (24x7).")
        s = sla.get_settings(conn)
        with st.form("settings"):
            vals = {k: st.number_input(k.replace("_", " "), min_value=1, value=int(v), step=1) for k, v in s.items()}
            if st.form_submit_button("Save settings"):
                for k, v in vals.items():
                    sla.update_setting(conn, k, v)
                st.success("Settings saved. New requests use the new SLA hours; existing deadlines are unchanged.")
