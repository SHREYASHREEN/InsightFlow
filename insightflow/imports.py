"""CSV import for requirements with validation, duplicate detection and a summary."""
import io
import pandas as pd
from . import config, requirements_service

REQUIRED = ["req_id", "title", "req_type", "priority", "status"]
OPTIONAL = ["description", "objective", "due_date", "dependencies", "owner", "analyst"]


def import_requirements_csv(conn, file_or_bytes, user="import"):
    """Import requirements. Returns summary dict: imported, duplicates, invalid, errors (list of strings)."""
    summary = {"imported": 0, "duplicates": 0, "invalid": 0, "errors": [], "rows": 0}
    try:
        raw = file_or_bytes.read() if hasattr(file_or_bytes, "read") else file_or_bytes
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8-sig")
        df = pd.read_csv(io.StringIO(raw), dtype=str, keep_default_na=False)
    except Exception as exc:
        summary["errors"].append(f"Could not read CSV: {exc}")
        return summary
    df.columns = [c.strip().lower() for c in df.columns]
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        summary["errors"].append("Missing required column(s): " + ", ".join(missing))
        return summary
    summary["rows"] = len(df)
    seen = set()
    objectives = {r["code"]: r["id"] for r in conn.execute("SELECT id, code FROM objectives")}
    owners = {r["name"]: r["id"] for r in conn.execute("SELECT id, name FROM stakeholders")}
    analysts = {r["username"].lower(): r["id"] for r in conn.execute("SELECT id, username FROM users")}
    for i, row in df.iterrows():
        line = i + 2  # header is line 1
        rid = row["req_id"].strip()
        if rid in seen or conn.execute("SELECT 1 FROM requirements WHERE req_id=?", (rid,)).fetchone():
            summary["duplicates"] += 1
            summary["errors"].append(f"Line {line}: duplicate requirement ID {rid} skipped.")
            continue
        seen.add(rid)
        get = lambda c: row[c].strip() if c in df.columns else ""
        data = {"req_id": rid, "title": row["title"], "description": get("description"),
                "req_type": row["req_type"].strip(), "priority": row["priority"].strip(),
                "status": row["status"].strip(), "due_date": get("due_date"), "dependencies": get("dependencies"),
                "objective_id": objectives.get(get("objective")), "owner_id": owners.get(get("owner")),
                "analyst_id": analysts.get(get("analyst").lower())}
        # Dependencies may reference rows later in the same file; they are re-checked after the first pass
        deps = data["dependencies"]
        data["dependencies"] = ""
        pk, errors = requirements_service.create_requirement(conn, data, user=user)
        if errors:
            summary["invalid"] += 1
            summary["errors"].append(f"Line {line}: " + "; ".join(errors))
            continue
        if deps:
            bad = [d for d in (x.strip() for x in deps.split(",")) if d and not conn.execute(
                "SELECT 1 FROM requirements WHERE req_id=?", (d,)).fetchone()]
            if bad:
                summary["errors"].append(f"Line {line}: unknown dependencies ignored: {', '.join(bad)}")
                deps = ",".join(d for d in (x.strip() for x in deps.split(",")) if d and d not in bad)
            if deps:
                with conn:
                    conn.execute("UPDATE requirements SET dependencies=? WHERE id=?", (deps, pk))
        summary["imported"] += 1
    return summary
