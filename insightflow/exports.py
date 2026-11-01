"""CSV / Excel / Markdown exports. Text cells that could be run as spreadsheet formulas are neutralised."""
import io
import pandas as pd
from . import kpis, requirements_service, sla, traceability, docs_service

FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def sanitize_cell(value):
    """Prefix a single quote to text starting with = + - @ TAB or CR so Excel/Sheets treat it as text."""
    if isinstance(value, str) and value.startswith(FORMULA_PREFIXES):
        return "'" + value
    return value


def sanitize_df(df):
    out = df.copy()
    for col in out.columns:
        if out[col].dtype == object or str(out[col].dtype).startswith("str"):
            out[col] = out[col].map(sanitize_cell)
    return out


def df_to_csv_bytes(df):
    return sanitize_df(df).to_csv(index=False).encode("utf-8")


def dfs_to_excel_bytes(sheets):
    """sheets: dict[str, DataFrame] -> .xlsx bytes (sheet names truncated to Excel's 31-char limit)."""
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        for name, df in sheets.items():
            safe = sanitize_df(df if len(df.columns) else pd.DataFrame({"info": ["No data"]}))
            safe.to_excel(writer, sheet_name=name[:31], index=False)
    return buf.getvalue()


def requirements_df(conn, **filters):
    rows = requirements_service.list_requirements(conn, **filters)
    cols = ["req_id", "title", "description", "req_type", "priority", "status", "objective", "owner", "analyst",
            "created_at", "due_date", "dependencies"]
    return pd.DataFrame(rows, columns=cols)


def requests_df(conn):
    return pd.DataFrame(sla.list_requests(conn))


def traceability_df(conn):
    return pd.DataFrame(traceability.build_matrix(conn))


def sla_summary_df(conn, now=None):
    s = sla.sla_summary(conn, now)
    return pd.DataFrame({"metric": list(s.keys()), "value": ["n/a" if v is None else v for v in s.values()]})


def requirements_markdown(conn):
    k = kpis.requirement_kpis(conn)
    lines = ["# Requirements Report", "", f"Total requirements: **{k['total_requirements']}**", "",
             "| Status | Count |", "|---|---|"]
    lines += [f"| {s} | {n} |" for s, n in sorted(k["by_status"].items())]
    lines += ["", "## Requirement list", "", "| ID | Title | Type | Priority | Status | Owner |", "|---|---|---|---|---|---|"]
    for r in requirements_service.list_requirements(conn):
        lines.append(f"| {r['req_id']} | {_md(r['title'])} | {r['req_type']} | {r['priority']} | {r['status']} | {r['owner'] or '-'} |")
    return "\n".join(lines) + "\n"


def traceability_markdown(conn):
    g = traceability.gap_report(conn)
    cov = traceability.coverage_summary(conn)
    lines = ["# Traceability Report", "", f"Requirements: {cov['total_requirements']}",
             f"Acceptance-criteria coverage: {cov['acceptance_criteria_coverage_pct']}%",
             f"UAT coverage: {cov['uat_coverage_pct']}%", "", "## Gaps", ""]
    for key, items in g.items():
        lines.append(f"- **{key.replace('_', ' ').title()}**: {len(items)}")
        for it in items:
            lines.append(f"  - {it.get('req_id') or it.get('code')}: {_md(it['title'])}")
    lines += ["", "## Matrix", "", "| Objective | Requirement | Story | Criterion | UAT test | UAT status |", "|---|---|---|---|---|---|"]
    for r in traceability.build_matrix(conn):
        lines.append("| " + " | ".join(_md(str(r[k]) if r[k] is not None else "-") for k in
                     ("objective", "requirement", "story", "criterion", "uat_test", "uat_status")) + " |")
    return "\n".join(lines) + "\n"


def sla_markdown(conn, now=None):
    s = sla.sla_summary(conn, now)
    bn = sla.bottleneck_analysis(conn, now)
    lines = ["# SLA Summary", "", "| Metric | Value |", "|---|---|"]
    lines += [f"| {k.replace('_', ' ')} | {'n/a' if v is None else v} |" for k, v in s.items()]
    lines += ["", "## Workflow stages (from recorded status history)", "", "| Stage | Visits | Avg hours | Total hours |", "|---|---|---|---|"]
    lines += [f"| {r['stage']} | {r['visits']} | {r['avg_hours']} | {r['total_hours']} |" for r in bn["stages"]]
    lines += ["", f"Bottleneck stage (highest average time): **{bn['bottleneck'] or 'n/a'}**"]
    return "\n".join(lines) + "\n"


def _md(text):
    return str(text).replace("|", "\\|").replace("\n", " ")
