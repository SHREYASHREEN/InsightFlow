"""Central configuration. Values can be overridden with environment variables."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = os.environ.get("INSIGHTFLOW_DB", str(BASE_DIR / "data" / "insightflow.db"))

REQ_STATUSES = ["Draft", "Proposed", "Approved", "In Progress", "In Review", "Completed", "Rejected"]
REQ_PRIORITIES = ["Critical", "High", "Medium", "Low"]
REQ_TYPES = ["Business", "Functional", "Non-Functional", "Stakeholder", "Transition"]

# Request workflow. The first four are "open" stages; Resolved and Closed are terminal.
REQUEST_STATUSES = ["New", "Assigned", "In Progress", "Pending Info", "Resolved", "Closed"]
OPEN_STATUSES = ["New", "Assigned", "In Progress", "Pending Info"]
TERMINAL_STATUSES = ["Resolved", "Closed"]
REQUEST_CATEGORIES = ["Access", "Hardware", "Software", "Network", "Data Request", "Other"]

# Default SLA targets in calendar hours (see docs/KPI_FORMULAS.md). Admin can change them.
DEFAULT_SETTINGS = {
    "sla_hours_Critical": "4",
    "sla_hours_High": "8",
    "sla_hours_Medium": "24",
    "sla_hours_Low": "72",
    "approaching_window_hours": "8",
}

DOC_SECTIONS = [
    "Problem Statement", "Business Objective", "Project Scope", "Functional Requirement",
    "Non-Functional Requirement", "Assumption", "Constraint", "Risk", "Dependency",
    "Process Flow", "Change Request",
]
UAT_STATUSES = ["Not Run", "Passed", "Failed", "Blocked"]
ROLES = ["Admin", "Business Analyst", "Viewer"]
