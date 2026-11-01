"""InsightFlow entry point.  Run with:  streamlit run app.py"""
import streamlit as st

st.set_page_config(page_title="InsightFlow", page_icon=":material/account_tree:", layout="wide")

from insightflow import auth, db, seed, ui  # noqa: E402

PAGES = {
    "Overview": (ui.page_overview, "view"),
    "Requirements": (ui.page_requirements, "view"),
    "Documentation": (ui.page_documentation, "view"),
    "Traceability": (ui.page_traceability, "view"),
    "Requests and SLA": (ui.page_requests, "view"),
    "Reports": (ui.page_reports, "view"),
    "Administration": (ui.page_admin, "user.manage"),
}


def main():
    conn = db.connect()
    try:
        db.init_db(conn)
        if conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
            seed.seed_users(conn)  # first run: create the documented demo accounts
        user = st.session_state.get("user")
        if not user:
            ui.login_page(conn)
            return
        ui.inject_css()
        with st.sidebar:
            st.markdown("## InsightFlow")
            st.caption(f"{user['full_name']} - {user['role']}")
            visible = [p for p, (_, perm) in PAGES.items() if auth.has_permission(user["role"], perm)]
            page = st.radio("Navigate", visible, label_visibility="collapsed")
            if st.button("Sign out"):
                st.session_state.pop("user", None)
                st.rerun()
            st.caption("Sample data only. Change demo passwords before real use.")
        func, perm = PAGES[page]
        if not auth.has_permission(user["role"], perm):  # defence in depth
            st.error("Access denied.")
            return
        func(conn, user)
    finally:
        conn.close()


main()
