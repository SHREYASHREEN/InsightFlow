"""Dashboard KPIs, all calculated from database rows."""
from . import sla, traceability


def requirement_kpis(conn):
    total = conn.execute("SELECT COUNT(*) FROM requirements").fetchone()[0]
    by_status = {r["status"]: r["n"] for r in conn.execute(
        "SELECT status, COUNT(*) AS n FROM requirements GROUP BY status")}
    by_priority_status = [dict(r) for r in conn.execute(
        "SELECT priority, status, COUNT(*) AS n FROM requirements GROUP BY priority, status")]
    gaps = traceability.gap_report(conn)
    return {"total_requirements": total, "by_status": by_status, "by_priority_status": by_priority_status,
            "missing_acceptance_criteria": len(gaps["no_acceptance_criteria"]),
            "missing_uat_tests": len(gaps["no_uat_tests"])}


def request_by_category(conn):
    return {r["category"]: r["n"] for r in conn.execute(
        "SELECT category, COUNT(*) AS n FROM requests GROUP BY category ORDER BY n DESC")}


def overview(conn, now=None):
    d = requirement_kpis(conn)
    d.update(sla.sla_summary(conn, now))
    return d
