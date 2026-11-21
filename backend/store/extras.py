"""Generated extras, saved with their tracker application."""
import json

from backend.models.extras import Extra, ExtraKind, ExtraUpdate
from backend.store.applications import NotFound, extra_from_row as _extra, get_row, timestamp
from backend.store.db import connect


def save_extra(application_id: int, kind: ExtraKind, subject: str | None, text: str,
               unverified: list[str]) -> Extra:
    with connect() as conn:
        get_row(conn, application_id)
        new_id = conn.execute(
            "INSERT INTO extras (application_id, kind, subject, text, unverified_json, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (application_id, kind, subject, text, json.dumps(unverified), timestamp()),
        ).lastrowid
        row = conn.execute("SELECT * FROM extras WHERE id = ?", (new_id,)).fetchone()
    return _extra(row)


def update_extra(extra_id: int, update: ExtraUpdate) -> Extra:
    """The user's own edits: saved as-is (they're the user's words, not the LLM's)."""
    with connect() as conn:
        if conn.execute("SELECT 1 FROM extras WHERE id = ?", (extra_id,)).fetchone() is None:
            raise NotFound(f"Extra {extra_id} not found")
        conn.execute("UPDATE extras SET text = ?, subject = ? WHERE id = ?", (update.text, update.subject, extra_id))
        row = conn.execute("SELECT * FROM extras WHERE id = ?", (extra_id,)).fetchone()
    return _extra(row)


def delete_extra(extra_id: int) -> None:
    with connect() as conn:
        if conn.execute("DELETE FROM extras WHERE id = ?", (extra_id,)).rowcount == 0:
            raise NotFound(f"Extra {extra_id} not found")
