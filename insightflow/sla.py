"""Request tracking, SLA and workflow metrics.

Rules (documented in docs/KPI_FORMULAS.md):
* Times are naive UTC; SLA uses calendar hours (24x7). No business-hours/holiday calendar.
* due_at = created_at + SLA hours for the priority (unless a due date is given).
* Every status change is stored in status_history. Stage durations come ONLY from those rows.
* resolved_at is set the first time status becomes Resolved or Closed.
"""
from datetime import timedelta
from . import config, timeutil


def get_settings(conn):
    return {r["key"]: r["value"] for r in conn.execute("SELECT key, value FROM settings")}


def update_setting(conn, key, value):
    if key not in config.DEFAULT_SETTINGS:
        raise ValueError("Unknown setting")
    if not str(value).strip().isdigit() or int(value) <= 0:
        raise ValueError("Setting must be a positive whole number")
    with conn:
        conn.execute("UPDATE settings SET value=? WHERE key=?", (str(int(value)), key))


def sla_hours_for(conn, priority):
    s = get_settings(conn)
    return int(s.get(f"sla_hours_{priority}", config.DEFAULT_SETTINGS.get(f"sla_hours_{priority}", "24")))


def validate_request(conn, data):
    errors = []
    if not (data.get("title") or "").strip():
        errors.append("Title is required.")
    if data.get("category") not in config.REQUEST_CATEGORIES:
        errors.append("Invalid category.")
    if data.get("priority") not in config.REQ_PRIORITIES:
        errors.append("Invalid priority.")
    if not (data.get("requester") or "").strip():
        errors.append("Requester is required.")
    if data.get("requirement_id") and not conn.execute(
            "SELECT 1 FROM requirements WHERE id=?", (data["requirement_id"],)).fetchone():
        errors.append("Linked requirement does not exist.")
    return errors


def next_request_id(conn):
    n = 0
    for r in conn.execute("SELECT request_id FROM requests"):
        try:
            n = max(n, int(r["request_id"].split("-")[1]))
        except (IndexError, ValueError):
            pass
    return f"RQ-{n + 1:04d}"


def create_request(conn, data, user="system", created_at=None):
    """Create a request and its first status-history row in one transaction. Returns (pk, errors)."""
    errors = validate_request(conn, data)
    if errors:
        return None, errors
    created = timeutil.parse(created_at) if created_at else timeutil.now_utc()
    due = timeutil.parse(data.get("due_at")) if data.get("due_at") else created + timedelta(
        hours=sla_hours_for(conn, data["priority"]))
    rid = data.get("request_id") or next_request_id(conn)
    if conn.execute("SELECT 1 FROM requests WHERE request_id=?", (rid,)).fetchone():
        return None, [f"Request {rid} already exists."]
    status = "Assigned" if data.get("owner") else "New"
    with conn:
        cur = conn.execute(
            """INSERT INTO requests(request_id,title,description,category,priority,requester,owner,created_at,
               due_at,status,resolved_at,requirement_id) VALUES (?,?,?,?,?,?,?,?,?,?,NULL,?)""",
            (rid, data["title"].strip(), data.get("description", ""), data["category"], data["priority"],
             data["requester"].strip(), data.get("owner") or None, timeutil.to_str(created), timeutil.to_str(due),
             status, data.get("requirement_id") or None))
        conn.execute("INSERT INTO status_history(request_pk,from_status,to_status,changed_at,changed_by)"
                     " VALUES (?,?,?,?,?)", (cur.lastrowid, None, "New", timeutil.to_str(created), user))
        if status != "New":
            conn.execute("INSERT INTO status_history(request_pk,from_status,to_status,changed_at,changed_by)"
                         " VALUES (?,?,?,?,?)", (cur.lastrowid, "New", status, timeutil.to_str(created), user))
    return cur.lastrowid, []


def change_status(conn, pk, new_status, user="system", at=None):
    """Move a request to a new status, recording history. Returns errors list."""
    if new_status not in config.REQUEST_STATUSES:
        return ["Invalid status."]
    row = conn.execute("SELECT * FROM requests WHERE id=?", (pk,)).fetchone()
    if row is None:
        return ["Request not found."]
    if row["status"] == new_status:
        return ["Request is already in that status."]
    when = timeutil.parse(at) if at else timeutil.now_utc()
    last = conn.execute("SELECT MAX(changed_at) FROM status_history WHERE request_pk=?", (pk,)).fetchone()[0]
    if last and when < timeutil.parse(last):
        return ["Status change time cannot be earlier than the previous change."]
    with conn:
        conn.execute("INSERT INTO status_history(request_pk,from_status,to_status,changed_at,changed_by)"
                     " VALUES (?,?,?,?,?)", (pk, row["status"], new_status, timeutil.to_str(when), user))
        resolved = row["resolved_at"]
        if new_status in config.TERMINAL_STATUSES and not resolved:
            resolved = timeutil.to_str(when)
        elif new_status in config.OPEN_STATUSES:
            resolved = None  # reopened
        conn.execute("UPDATE requests SET status=?, resolved_at=? WHERE id=?", (new_status, resolved, pk))
    return []


def assign_owner(conn, pk, owner, user="system"):
    with conn:
        conn.execute("UPDATE requests SET owner=? WHERE id=?", (owner or None, pk))
    row = conn.execute("SELECT status FROM requests WHERE id=?", (pk,)).fetchone()
    if row and row["status"] == "New" and owner:
        change_status(conn, pk, "Assigned", user)


def delete_request(conn, pk):
    with conn:
        cur = conn.execute("DELETE FROM requests WHERE id=?", (pk,))
    return cur.rowcount > 0


def list_requests(conn):
    return [dict(r) for r in conn.execute("SELECT * FROM requests ORDER BY created_at DESC, id DESC")]


# --------------------------- metrics ---------------------------------------
def classify(row, now, approaching_hours=8):
    """Return 'completed', 'overdue', 'approaching' or 'on_track' for one request row."""
    if row["status"] in config.TERMINAL_STATUSES:
        return "completed"
    due = timeutil.parse(row["due_at"])
    if now > due:
        return "overdue"
    if (due - now) <= timedelta(hours=approaching_hours):
        return "approaching"
    return "on_track"


def request_buckets(conn, now=None):
    now = now or timeutil.now_utc()
    window = int(get_settings(conn).get("approaching_window_hours", 8))
    buckets = {"overdue": [], "approaching": [], "on_track": [], "completed": []}
    for r in list_requests(conn):
        buckets[classify(r, now, window)].append(r)
    return buckets


def sla_summary(conn, now=None):
    """SLA compliance % = resolved_on_time / resolved_total * 100 (None if nothing resolved).
    Average resolution hours = mean(resolved_at - created_at) for resolved requests."""
    now = now or timeutil.now_utc()
    rows = list_requests(conn)
    resolved = [r for r in rows if r["resolved_at"]]
    met = [r for r in resolved if timeutil.parse(r["resolved_at"]) <= timeutil.parse(r["due_at"])]
    hours = [timeutil.hours_between(timeutil.parse(r["created_at"]), timeutil.parse(r["resolved_at"])) for r in resolved]
    b = request_buckets(conn, now)
    return {
        "total_requests": len(rows),
        "open_requests": len(b["overdue"]) + len(b["approaching"]) + len(b["on_track"]),
        "overdue_requests": len(b["overdue"]),
        "approaching_deadline": len(b["approaching"]),
        "completed_requests": len(resolved),
        "resolved_on_time": len(met),
        "sla_compliance_pct": None if not resolved else round(100.0 * len(met) / len(resolved), 1),
        "avg_resolution_hours": None if not hours else round(sum(hours) / len(hours), 2),
    }


def stage_durations(conn, now=None):
    """Hours spent in each OPEN stage, computed from consecutive status_history rows.
    Returns list of dicts {request_id, stage, hours}. The stage a request is currently in counts up to `now`."""
    now = now or timeutil.now_utc()
    out = []
    reqs = {r["id"]: r for r in conn.execute("SELECT id, request_id FROM requests")}
    hist = {}
    for h in conn.execute("SELECT * FROM status_history ORDER BY request_pk, changed_at, id"):
        hist.setdefault(h["request_pk"], []).append(h)
    for pk, events in hist.items():
        for i, ev in enumerate(events):
            if ev["to_status"] not in config.OPEN_STATUSES:
                continue
            start = timeutil.parse(ev["changed_at"])
            end = timeutil.parse(events[i + 1]["changed_at"]) if i + 1 < len(events) else now
            out.append({"request_id": reqs[pk]["request_id"], "stage": ev["to_status"],
                        "hours": round(timeutil.hours_between(start, end), 2)})
    return out


def bottleneck_analysis(conn, now=None):
    """Average and total hours per open stage. The bottleneck is the stage with the highest average."""
    durs = stage_durations(conn, now)
    agg = {}
    for d in durs:
        a = agg.setdefault(d["stage"], {"stage": d["stage"], "visits": 0, "total_hours": 0.0})
        a["visits"] += 1
        a["total_hours"] += d["hours"]
    rows = []
    for stage in config.OPEN_STATUSES:
        if stage in agg:
            a = agg[stage]
            rows.append({"stage": stage, "visits": a["visits"], "total_hours": round(a["total_hours"], 2),
                         "avg_hours": round(a["total_hours"] / a["visits"], 2)})
    bottleneck = max(rows, key=lambda r: r["avg_hours"])["stage"] if rows else None
    return {"stages": rows, "bottleneck": bottleneck}


def overdue_by_owner(conn, now=None):
    counts = {}
    for r in request_buckets(conn, now)["overdue"]:
        k = r["owner"] or "Unassigned"
        counts[k] = counts.get(k, 0) + 1
    return counts


def compliance_trend(conn):
    """SLA compliance per month of resolution (only months that have resolved requests)."""
    by_month = {}
    for r in list_requests(conn):
        if not r["resolved_at"]:
            continue
        m = r["resolved_at"][:7]
        ok = timeutil.parse(r["resolved_at"]) <= timeutil.parse(r["due_at"])
        t = by_month.setdefault(m, [0, 0])
        t[0] += 1 if ok else 0
        t[1] += 1
    return [{"month": m, "resolved": t[1], "on_time": t[0], "compliance_pct": round(100.0 * t[0] / t[1], 1)}
            for m, t in sorted(by_month.items())]
