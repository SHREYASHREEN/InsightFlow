"""SQLite connection helper and schema creation (all SQL here is parameter-free DDL)."""
import sqlite3
from pathlib import Path
from . import config

SCHEMA_VERSION = 1

SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_info (version INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE COLLATE NOCASE,
    full_name TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('Admin','Business Analyst','Viewer')),
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0,1)),
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS objectives (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS stakeholders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    role TEXT NOT NULL DEFAULT '',
    department TEXT NOT NULL DEFAULT '',
    influence TEXT NOT NULL DEFAULT 'Medium' CHECK (influence IN ('High','Medium','Low')),
    interest TEXT NOT NULL DEFAULT 'Medium' CHECK (interest IN ('High','Medium','Low'))
);
CREATE TABLE IF NOT EXISTS requirements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    req_id TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    objective_id INTEGER REFERENCES objectives(id) ON DELETE SET NULL,
    req_type TEXT NOT NULL,
    priority TEXT NOT NULL,
    status TEXT NOT NULL,
    owner_id INTEGER REFERENCES stakeholders(id) ON DELETE SET NULL,
    analyst_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL,
    due_date TEXT,
    dependencies TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS requirement_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    requirement_id INTEGER NOT NULL REFERENCES requirements(id) ON DELETE CASCADE,
    changed_at TEXT NOT NULL,
    changed_by TEXT NOT NULL,
    field TEXT NOT NULL,
    old_value TEXT,
    new_value TEXT
);
CREATE TABLE IF NOT EXISTS user_stories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    story_id TEXT NOT NULL UNIQUE,
    requirement_id INTEGER NOT NULL REFERENCES requirements(id) ON DELETE CASCADE,
    as_a TEXT NOT NULL,
    i_want TEXT NOT NULL,
    so_that TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS acceptance_criteria (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    requirement_id INTEGER NOT NULL REFERENCES requirements(id) ON DELETE CASCADE,
    story_id INTEGER REFERENCES user_stories(id) ON DELETE SET NULL,
    given_text TEXT NOT NULL DEFAULT '',
    when_text TEXT NOT NULL DEFAULT '',
    then_text TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    CHECK (length(given_text || when_text || then_text || description) > 0)
);
CREATE TABLE IF NOT EXISTS uat_tests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    test_id TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    steps TEXT NOT NULL DEFAULT '',
    expected_result TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'Not Run' CHECK (status IN ('Not Run','Passed','Failed','Blocked')),
    requirement_id INTEGER NOT NULL REFERENCES requirements(id) ON DELETE CASCADE,
    criterion_id INTEGER REFERENCES acceptance_criteria(id) ON DELETE SET NULL
);
CREATE TABLE IF NOT EXISTS doc_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    section TEXT NOT NULL,
    title TEXT NOT NULL,
    content TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    category TEXT NOT NULL,
    priority TEXT NOT NULL,
    requester TEXT NOT NULL,
    owner TEXT,
    created_at TEXT NOT NULL,
    due_at TEXT NOT NULL,
    status TEXT NOT NULL,
    resolved_at TEXT,
    requirement_id INTEGER REFERENCES requirements(id) ON DELETE SET NULL
);
CREATE TABLE IF NOT EXISTS status_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_pk INTEGER NOT NULL REFERENCES requests(id) ON DELETE CASCADE,
    from_status TEXT,
    to_status TEXT NOT NULL,
    changed_at TEXT NOT NULL,
    changed_by TEXT NOT NULL DEFAULT 'system'
);
CREATE INDEX IF NOT EXISTS idx_req_status ON requirements(status);
CREATE INDEX IF NOT EXISTS idx_hist_req ON status_history(request_pk, changed_at);
CREATE INDEX IF NOT EXISTS idx_requests_status ON requests(status);
"""


def connect(path=None):
    """Open a connection with foreign keys enforced and dict-like rows."""
    path = str(path or config.DB_PATH)
    if path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn):
    """Create tables and default settings. Safe to call on every start-up."""
    with conn:
        conn.executescript(SCHEMA)
        row = conn.execute("SELECT version FROM schema_info").fetchone()
        if row is None:
            conn.execute("INSERT INTO schema_info(version) VALUES (?)", (SCHEMA_VERSION,))
        for k, v in config.DEFAULT_SETTINGS.items():
            conn.execute("INSERT OR IGNORE INTO settings(key, value) VALUES (?, ?)", (k, v))
    conn.execute("PRAGMA foreign_keys = ON")


def table_names(conn):
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall()
    return sorted(r["name"] for r in rows)
