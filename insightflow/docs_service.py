"""Objectives, stakeholders, user stories, acceptance criteria, UAT tests and BA documentation items."""
import re
from . import config, timeutil

CODE_RE = re.compile(r"^[A-Z]{2,5}-\d{1,5}$")


def _now():
    return timeutil.to_str(timeutil.now_utc())


# ---- Objectives -----------------------------------------------------------
def add_objective(conn, code, title, description=""):
    code, title = (code or "").strip(), (title or "").strip()
    errors = []
    if not CODE_RE.match(code):
        errors.append("Objective code must look like OBJ-01.")
    if not title:
        errors.append("Objective title is required.")
    if not errors and conn.execute("SELECT 1 FROM objectives WHERE code=?", (code,)).fetchone():
        errors.append(f"Objective {code} already exists.")
    if errors:
        return None, errors
    with conn:
        cur = conn.execute("INSERT INTO objectives(code,title,description,created_at) VALUES (?,?,?,?)",
                           (code, title, description or "", _now()))
    return cur.lastrowid, []


def list_objectives(conn):
    return [dict(r) for r in conn.execute("SELECT * FROM objectives ORDER BY code")]


def delete_objective(conn, pk):
    with conn:
        conn.execute("DELETE FROM objectives WHERE id=?", (pk,))


# ---- Stakeholders ---------------------------------------------------------
def add_stakeholder(conn, name, role="", department="", influence="Medium", interest="Medium"):
    name = (name or "").strip()
    if not name:
        return None, ["Stakeholder name is required."]
    if influence not in ("High", "Medium", "Low") or interest not in ("High", "Medium", "Low"):
        return None, ["Influence and interest must be High, Medium or Low."]
    if conn.execute("SELECT 1 FROM stakeholders WHERE name=?", (name,)).fetchone():
        return None, [f"Stakeholder {name} already exists."]
    with conn:
        cur = conn.execute("INSERT INTO stakeholders(name,role,department,influence,interest) VALUES (?,?,?,?,?)",
                           (name, role, department, influence, interest))
    return cur.lastrowid, []


def list_stakeholders(conn):
    return [dict(r) for r in conn.execute("SELECT * FROM stakeholders ORDER BY name")]


def delete_stakeholder(conn, pk):
    with conn:
        conn.execute("DELETE FROM stakeholders WHERE id=?", (pk,))


# ---- User stories ---------------------------------------------------------
def format_story(as_a, i_want, so_that):
    return f"As a {as_a}, I want {i_want}, so that {so_that}."


def add_story(conn, story_id, requirement_id, as_a, i_want, so_that):
    story_id = (story_id or "").strip()
    errors = []
    if not re.match(r"^US-\d{1,5}$", story_id):
        errors.append("Story ID must look like US-001.")
    for label, v in (("'As a'", as_a), ("'I want'", i_want), ("'So that'", so_that)):
        if not (v or "").strip():
            errors.append(f"{label} part of the story is required.")
    if not conn.execute("SELECT 1 FROM requirements WHERE id=?", (requirement_id,)).fetchone():
        errors.append("Linked requirement does not exist.")
    if not errors and conn.execute("SELECT 1 FROM user_stories WHERE story_id=?", (story_id,)).fetchone():
        errors.append(f"Story {story_id} already exists.")
    if errors:
        return None, errors
    with conn:
        cur = conn.execute("INSERT INTO user_stories(story_id,requirement_id,as_a,i_want,so_that) VALUES (?,?,?,?,?)",
                           (story_id, requirement_id, as_a.strip(), i_want.strip(), so_that.strip()))
    return cur.lastrowid, []


def list_stories(conn):
    rows = conn.execute("""SELECT s.*, r.req_id FROM user_stories s JOIN requirements r ON r.id = s.requirement_id
                           ORDER BY s.story_id""")
    out = []
    for r in rows:
        d = dict(r)
        d["text"] = format_story(d["as_a"], d["i_want"], d["so_that"])
        out.append(d)
    return out


def delete_story(conn, pk):
    with conn:
        conn.execute("DELETE FROM user_stories WHERE id=?", (pk,))


# ---- Acceptance criteria --------------------------------------------------
def add_criterion(conn, requirement_id, given="", when="", then="", description="", story_id=None):
    given, when, then, description = [(x or "").strip() for x in (given, when, then, description)]
    errors = []
    if not (given or when or then or description):
        errors.append("Provide Given/When/Then text or a plain description.")
    if (given or when or then) and not (given and when and then):
        errors.append("Given, When and Then must all be filled in for the Given/When/Then format.")
    if not conn.execute("SELECT 1 FROM requirements WHERE id=?", (requirement_id,)).fetchone():
        errors.append("Linked requirement does not exist.")
    if errors:
        return None, errors
    with conn:
        cur = conn.execute("INSERT INTO acceptance_criteria(requirement_id,story_id,given_text,when_text,then_text,"
                           "description) VALUES (?,?,?,?,?,?)",
                           (requirement_id, story_id or None, given, when, then, description))
    return cur.lastrowid, []


def criterion_text(row):
    if row["given_text"]:
        return f"Given {row['given_text']}, when {row['when_text']}, then {row['then_text']}"
    return row["description"]


def list_criteria(conn):
    out = []
    for r in conn.execute("""SELECT c.*, r.req_id FROM acceptance_criteria c JOIN requirements r
                             ON r.id = c.requirement_id ORDER BY r.req_id, c.id"""):
        d = dict(r)
        d["text"] = criterion_text(r)
        out.append(d)
    return out


def delete_criterion(conn, pk):
    with conn:
        conn.execute("DELETE FROM acceptance_criteria WHERE id=?", (pk,))


# ---- UAT tests ------------------------------------------------------------
def add_uat_test(conn, test_id, title, requirement_id, steps="", expected="", status="Not Run", criterion_id=None):
    test_id, title = (test_id or "").strip(), (title or "").strip()
    errors = []
    if not re.match(r"^UAT-\d{1,5}$", test_id):
        errors.append("Test ID must look like UAT-001.")
    if not title:
        errors.append("Test title is required.")
    if status not in config.UAT_STATUSES:
        errors.append("Invalid test status.")
    if not conn.execute("SELECT 1 FROM requirements WHERE id=?", (requirement_id,)).fetchone():
        errors.append("Linked requirement does not exist.")
    if not errors and conn.execute("SELECT 1 FROM uat_tests WHERE test_id=?", (test_id,)).fetchone():
        errors.append(f"Test {test_id} already exists.")
    if errors:
        return None, errors
    with conn:
        cur = conn.execute("INSERT INTO uat_tests(test_id,title,steps,expected_result,status,requirement_id,"
                           "criterion_id) VALUES (?,?,?,?,?,?,?)",
                           (test_id, title, steps, expected, status, requirement_id, criterion_id or None))
    return cur.lastrowid, []


def list_uat_tests(conn):
    return [dict(r) for r in conn.execute(
        "SELECT t.*, r.req_id FROM uat_tests t JOIN requirements r ON r.id=t.requirement_id ORDER BY t.test_id")]


def set_uat_status(conn, pk, status):
    if status not in config.UAT_STATUSES:
        raise ValueError("Invalid test status")
    with conn:
        conn.execute("UPDATE uat_tests SET status=? WHERE id=?", (status, pk))


def delete_uat_test(conn, pk):
    with conn:
        conn.execute("DELETE FROM uat_tests WHERE id=?", (pk,))


# ---- BA documentation items ----------------------------------------------
def add_doc_item(conn, section, title, content=""):
    if section not in config.DOC_SECTIONS:
        return None, ["Unknown documentation section."]
    if not (title or "").strip():
        return None, ["Title is required."]
    with conn:
        cur = conn.execute("INSERT INTO doc_items(section,title,content,created_at) VALUES (?,?,?,?)",
                           (section, title.strip(), content or "", _now()))
    return cur.lastrowid, []


def list_doc_items(conn, section=None):
    if section:
        rows = conn.execute("SELECT * FROM doc_items WHERE section=? ORDER BY id", (section,))
    else:
        rows = conn.execute("SELECT * FROM doc_items ORDER BY section, id")
    return [dict(r) for r in rows]


def delete_doc_item(conn, pk):
    with conn:
        conn.execute("DELETE FROM doc_items WHERE id=?", (pk,))
