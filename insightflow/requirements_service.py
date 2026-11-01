"""Requirement CRUD, validation, search/filter/sort and change history."""
import re
from . import config, timeutil

REQ_ID_RE = re.compile(r"^[A-Z]{2,5}-\d{1,5}$")
SORT_COLUMNS = {"req_id": "r.req_id", "title": "r.title", "priority": "priority_rank", "status": "r.status",
                "due_date": "r.due_date", "created_at": "r.created_at"}
TRACKED = ["title", "description", "objective_id", "req_type", "priority", "status", "owner_id",
           "analyst_id", "due_date", "dependencies"]


def validate_requirement(conn, data, editing_id=None):
    """Return a list of error strings (empty list = valid)."""
    errors = []
    req_id = (data.get("req_id") or "").strip()
    if not REQ_ID_RE.match(req_id):
        errors.append("Requirement ID must look like REQ-001 (2-5 capital letters, a dash, digits).")
    else:
        row = conn.execute("SELECT id FROM requirements WHERE req_id = ?", (req_id,)).fetchone()
        if row and row["id"] != editing_id:
            errors.append(f"Requirement ID {req_id} already exists.")
    title = (data.get("title") or "").strip()
    if not title:
        errors.append("Title is required.")
    elif len(title) > 150:
        errors.append("Title must be 150 characters or fewer.")
    if data.get("req_type") not in config.REQ_TYPES:
        errors.append("Invalid requirement type.")
    if data.get("priority") not in config.REQ_PRIORITIES:
        errors.append("Invalid priority.")
    if data.get("status") not in config.REQ_STATUSES:
        errors.append("Invalid status.")
    due = data.get("due_date")
    if due not in (None, ""):
        try:
            timeutil.parse(due)
        except ValueError:
            errors.append("Due date must be in YYYY-MM-DD format.")
    deps = [d.strip() for d in (data.get("dependencies") or "").split(",") if d.strip()]
    for d in deps:
        if d == req_id:
            errors.append("A requirement cannot depend on itself.")
        elif not conn.execute("SELECT 1 FROM requirements WHERE req_id = ?", (d,)).fetchone():
            errors.append(f"Dependency {d} does not exist.")
    return errors


def next_req_id(conn, prefix="REQ"):
    n = 0
    for r in conn.execute("SELECT req_id FROM requirements WHERE req_id LIKE ?", (prefix + "-%",)):
        try:
            n = max(n, int(r["req_id"].split("-")[1]))
        except (IndexError, ValueError):
            pass
    return f"{prefix}-{n + 1:03d}"


def _clean(data):
    out = dict(data)
    for k in ("req_id", "title", "description", "dependencies"):
        out[k] = (out.get(k) or "").strip()
    out["due_date"] = (out.get("due_date") or None) or None
    for k in ("objective_id", "owner_id", "analyst_id"):
        out[k] = out.get(k) or None
    return out


def create_requirement(conn, data, user="system", created_at=None):
    """Returns (pk, errors)."""
    data = _clean(data)
    errors = validate_requirement(conn, data)
    if errors:
        return None, errors
    now = created_at or timeutil.to_str(timeutil.now_utc())
    with conn:
        cur = conn.execute(
            """INSERT INTO requirements(req_id,title,description,objective_id,req_type,priority,status,
               owner_id,analyst_id,created_at,due_date,dependencies) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (data["req_id"], data["title"], data["description"], data["objective_id"], data["req_type"],
             data["priority"], data["status"], data["owner_id"], data["analyst_id"], now, data["due_date"],
             data["dependencies"]))
        conn.execute("INSERT INTO requirement_history(requirement_id,changed_at,changed_by,field,old_value,new_value)"
                     " VALUES (?,?,?,?,?,?)", (cur.lastrowid, now, user, "created", None, data["req_id"]))
    return cur.lastrowid, []


def get_requirement(conn, pk):
    row = conn.execute("SELECT * FROM requirements WHERE id = ?", (pk,)).fetchone()
    return dict(row) if row else None


def update_requirement(conn, pk, data, user="system"):
    """Edits a requirement and writes one history row per changed field. Returns errors list."""
    old = get_requirement(conn, pk)
    if old is None:
        return ["Requirement not found."]
    data = _clean(data)
    errors = validate_requirement(conn, data, editing_id=pk)
    if errors:
        return errors
    now = timeutil.to_str(timeutil.now_utc())
    with conn:
        conn.execute(
            """UPDATE requirements SET req_id=?, title=?, description=?, objective_id=?, req_type=?, priority=?,
               status=?, owner_id=?, analyst_id=?, due_date=?, dependencies=? WHERE id=?""",
            (data["req_id"], data["title"], data["description"], data["objective_id"], data["req_type"],
             data["priority"], data["status"], data["owner_id"], data["analyst_id"], data["due_date"],
             data["dependencies"], pk))
        for f in TRACKED:
            if (old[f] or None) != (data.get(f) or None):
                conn.execute("INSERT INTO requirement_history(requirement_id,changed_at,changed_by,field,"
                             "old_value,new_value) VALUES (?,?,?,?,?,?)",
                             (pk, now, user, f, None if old[f] is None else str(old[f]),
                              None if data.get(f) is None else str(data.get(f))))
    return []


def delete_requirement(conn, pk):
    """Delete a requirement. Stories, criteria, tests and history cascade; linked requests are unlinked."""
    with conn:
        cur = conn.execute("DELETE FROM requirements WHERE id = ?", (pk,))
    return cur.rowcount > 0


def list_requirements(conn, search="", priority=None, status=None, owner_id=None,
                      date_from=None, date_to=None, sort_by="req_id", descending=False):
    """Search + filter + sort using only parameterised SQL (sort column is whitelisted)."""
    sql = """SELECT r.id, r.req_id, r.title, r.description, r.req_type, r.priority, r.status, r.due_date,
                    r.created_at, r.dependencies, r.objective_id, r.owner_id, r.analyst_id,
                    o.code AS objective, s.name AS owner, u.full_name AS analyst,
                    CASE r.priority WHEN 'Critical' THEN 1 WHEN 'High' THEN 2 WHEN 'Medium' THEN 3 ELSE 4 END AS priority_rank
             FROM requirements r
             LEFT JOIN objectives o ON o.id = r.objective_id
             LEFT JOIN stakeholders s ON s.id = r.owner_id
             LEFT JOIN users u ON u.id = r.analyst_id WHERE 1=1"""
    params = []
    if search:
        like = f"%{search.strip()}%"
        sql += " AND (r.req_id LIKE ? OR r.title LIKE ? OR r.description LIKE ?)"
        params += [like, like, like]
    if priority:
        sql += f" AND r.priority IN ({','.join('?' * len(priority))})"
        params += list(priority)
    if status:
        sql += f" AND r.status IN ({','.join('?' * len(status))})"
        params += list(status)
    if owner_id:
        sql += " AND r.owner_id = ?"
        params.append(owner_id)
    if date_from:
        sql += " AND date(r.created_at) >= date(?)"
        params.append(str(date_from))
    if date_to:
        sql += " AND date(r.created_at) <= date(?)"
        params.append(str(date_to))
    col = SORT_COLUMNS.get(sort_by, "r.req_id")
    sql += f" ORDER BY {col} {'DESC' if descending else 'ASC'}, r.req_id ASC"
    return [dict(r) for r in conn.execute(sql, params)]


def requirement_history(conn, pk):
    return [dict(r) for r in conn.execute(
        "SELECT changed_at, changed_by, field, old_value, new_value FROM requirement_history "
        "WHERE requirement_id = ? ORDER BY id DESC", (pk,))]
