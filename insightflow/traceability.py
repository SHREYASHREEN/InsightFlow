"""Traceability: Objective -> Requirement -> User story -> Acceptance criterion -> UAT test.
Everything is computed from database rows; nothing is hard-coded."""
from . import config


def build_matrix(conn):
    """One row per path through the chain (LEFT JOINs so gaps are visible as None)."""
    sql = """
    SELECT o.code AS objective, r.req_id AS requirement, r.title AS requirement_title, r.status AS req_status,
           s.story_id AS story, c.id AS criterion_id,
           CASE WHEN c.id IS NULL THEN NULL
                WHEN c.given_text != '' THEN 'Given ' || c.given_text || ', when ' || c.when_text || ', then ' || c.then_text
                ELSE c.description END AS criterion,
           t.test_id AS uat_test, t.status AS uat_status
    FROM requirements r
    LEFT JOIN objectives o ON o.id = r.objective_id
    LEFT JOIN user_stories s ON s.requirement_id = r.id
    LEFT JOIN acceptance_criteria c ON c.requirement_id = r.id AND (c.story_id IS s.id OR s.id IS NULL OR c.story_id IS NULL)
    LEFT JOIN uat_tests t ON t.requirement_id = r.id AND (t.criterion_id IS c.id OR t.criterion_id IS NULL)
    ORDER BY o.code, r.req_id, s.story_id, c.id, t.test_id"""
    rows = [dict(r) for r in conn.execute(sql)]
    seen, out = set(), []
    for r in rows:  # remove exact duplicate paths
        key = (r["objective"], r["requirement"], r["story"], r["criterion_id"], r["uat_test"])
        if key not in seen:
            seen.add(key)
            out.append(r)
    return out


def gap_report(conn):
    """Dictionary of lists describing traceability gaps."""
    no_ac = [dict(r) for r in conn.execute(
        """SELECT req_id, title, status FROM requirements r
           WHERE NOT EXISTS (SELECT 1 FROM acceptance_criteria c WHERE c.requirement_id = r.id) ORDER BY req_id""")]
    no_tests = [dict(r) for r in conn.execute(
        """SELECT req_id, title, status FROM requirements r
           WHERE NOT EXISTS (SELECT 1 FROM uat_tests t WHERE t.requirement_id = r.id) ORDER BY req_id""")]
    no_story = [dict(r) for r in conn.execute(
        """SELECT req_id, title, status FROM requirements r
           WHERE NOT EXISTS (SELECT 1 FROM user_stories s WHERE s.requirement_id = r.id) ORDER BY req_id""")]
    no_req_obj = [dict(r) for r in conn.execute(
        """SELECT code, title FROM objectives o
           WHERE NOT EXISTS (SELECT 1 FROM requirements r WHERE r.objective_id = o.id) ORDER BY code""")]
    no_objective = [dict(r) for r in conn.execute(
        "SELECT req_id, title, status FROM requirements WHERE objective_id IS NULL ORDER BY req_id")]
    unapproved = [dict(r) for r in conn.execute(
        "SELECT req_id, title, status FROM requirements WHERE status IN ('Draft','Proposed') ORDER BY req_id")]
    return {"no_acceptance_criteria": no_ac, "no_uat_tests": no_tests, "no_user_story": no_story,
            "objectives_without_requirements": no_req_obj, "requirements_without_objective": no_objective,
            "unapproved_or_incomplete": unapproved}


def coverage_summary(conn):
    total = conn.execute("SELECT COUNT(*) FROM requirements").fetchone()[0]
    g = gap_report(conn)
    def pct(missing):
        return None if total == 0 else round(100.0 * (total - len(missing)) / total, 1)
    return {"total_requirements": total,
            "acceptance_criteria_coverage_pct": pct(g["no_acceptance_criteria"]),
            "uat_coverage_pct": pct(g["no_uat_tests"]),
            "user_story_coverage_pct": pct(g["no_user_story"]),
            "objectives_without_requirements": len(g["objectives_without_requirements"])}
