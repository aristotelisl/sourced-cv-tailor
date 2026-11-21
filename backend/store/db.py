"""SQLite connection and schema. The database file is git-ignored (*.db)."""
import sqlite3
from contextlib import contextmanager
from collections.abc import Iterator

from backend.config import get_settings

SCHEMA_VERSION = 3  # bump when SCHEMA changes; every statement is idempotent
SCHEMA = """
CREATE TABLE IF NOT EXISTS applications (
    id INTEGER PRIMARY KEY,
    company TEXT,
    title TEXT NOT NULL,
    url TEXT,
    location TEXT,
    salary_json TEXT,
    status TEXT NOT NULL DEFAULT 'draft',
    applied_at TEXT,
    cv_version_id INTEGER REFERENCES cv_versions(id) ON DELETE SET NULL,
    notes TEXT NOT NULL DEFAULT '',
    contacts TEXT NOT NULL DEFAULT '',
    job_text TEXT NOT NULL,
    analysis_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS cv_versions (
    id INTEGER PRIMARY KEY,
    application_id INTEGER NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    label TEXT NOT NULL,
    filename TEXT NOT NULL,
    cv_json TEXT NOT NULL,
    coverage_json TEXT NOT NULL DEFAULT '[]',
    suggestions_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS cv_versions_by_application ON cv_versions(application_id);
CREATE TABLE IF NOT EXISTS extras (
    id INTEGER PRIMARY KEY,
    application_id INTEGER NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    kind TEXT NOT NULL,
    subject TEXT,
    text TEXT NOT NULL,
    unverified_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS extras_by_application ON extras(application_id);
CREATE TABLE IF NOT EXISTS llm_usage (
    id INTEGER PRIMARY KEY,
    created_at TEXT NOT NULL,
    task TEXT NOT NULL,
    model TEXT NOT NULL,
    effort TEXT NOT NULL,
    input_tokens INTEGER NOT NULL,
    output_tokens INTEGER NOT NULL,
    cache_read_tokens INTEGER NOT NULL,
    cache_write_tokens INTEGER NOT NULL,
    cost_usd REAL
);
"""


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    """A connection with foreign keys on and the schema in place; commits on success."""
    path = get_settings().db_path
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        if conn.execute("PRAGMA user_version").fetchone()[0] < SCHEMA_VERSION:
            conn.executescript(SCHEMA)
            conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        yield conn
        conn.commit()
    finally:
        conn.close()
