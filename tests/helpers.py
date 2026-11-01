import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from insightflow import db  # noqa: E402


def memory_db():
    conn = db.connect(":memory:")
    db.init_db(conn)
    return conn


def req(**kw):
    d = dict(req_id="REQ-001", title="Test requirement", description="d", req_type="Functional",
             priority="High", status="Draft")
    d.update(kw)
    return d


def request(**kw):
    d = dict(title="Reset password", category="Access", priority="High", requester="Tester", owner="")
    d.update(kw)
    return d
