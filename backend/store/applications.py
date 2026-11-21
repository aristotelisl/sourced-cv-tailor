"""Applications and CV versions in SQLite. Every function opens its own short connection."""
import json
import sqlite3
from datetime import date, datetime

from backend.models import JobAnalysis, Salary, TailoredCV
from backend.models.extras import Extra
from backend.models.tracker import (
    Application, ApplicationCreate, ApplicationDetail, ApplicationSummary, ApplicationUpdate, CvVersion,
    CvVersionCreate, CvVersionSummary,
)
from backend.store.db import connect


class NotFound(LookupError):
    pass


def timestamp() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _application(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"], "company": row["company"], "title": row["title"], "url": row["url"],
        "location": row["location"],
        "salary": Salary.model_validate_json(row["salary_json"]) if row["salary_json"] else None,
        "status": row["status"], "applied_at": row["applied_at"], "cv_version_id": row["cv_version_id"],
        "notes": row["notes"], "contacts": row["contacts"],
        "created_at": row["created_at"], "updated_at": row["updated_at"],
    }


def _version_summary(row: sqlite3.Row) -> CvVersionSummary:
    return CvVersionSummary(id=row["id"], application_id=row["application_id"], label=row["label"],
                            filename=row["filename"], created_at=row["created_at"])


def extra_from_row(row: sqlite3.Row) -> Extra:
    return Extra(id=row["id"], kind=row["kind"], subject=row["subject"], text=row["text"],
                 unverified_used=json.loads(row["unverified_json"]), created_at=row["created_at"])


def get_row(conn: sqlite3.Connection, application_id: int) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM applications WHERE id = ?", (application_id,)).fetchone()
    if row is None:
        raise NotFound(f"Application {application_id} not found")
    return row


def create_application(data: ApplicationCreate) -> ApplicationDetail:
    job = data.analysis
    now = timestamp()
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO applications (company, title, url, location, salary_json, job_text, analysis_json,"
            " created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (job.company, job.title, data.url, job.location, job.salary.model_dump_json() if job.salary else None,
             data.job_text, job.model_dump_json(), now, now),
        )
        new_id = cur.lastrowid
    return get_application(new_id)


def list_applications() -> list[ApplicationSummary]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT a.*, COUNT(v.id) AS version_count, MAX(v.id) AS latest_version_id"
            " FROM applications a LEFT JOIN cv_versions v ON v.application_id = a.id"
            " GROUP BY a.id ORDER BY a.updated_at DESC, a.id DESC"
        ).fetchall()
    return [ApplicationSummary(**_application(r), version_count=r["version_count"],
                               latest_version_id=r["latest_version_id"]) for r in rows]


def get_application(application_id: int) -> ApplicationDetail:
    with connect() as conn:
        row = get_row(conn, application_id)
        versions = conn.execute("SELECT * FROM cv_versions WHERE application_id = ? ORDER BY id DESC",
                                (application_id,)).fetchall()
        extras = conn.execute("SELECT * FROM extras WHERE application_id = ? ORDER BY id DESC",
                              (application_id,)).fetchall()
    return ApplicationDetail(**_application(row), job_text=row["job_text"],
                             analysis=JobAnalysis.model_validate_json(row["analysis_json"]),
                             versions=[_version_summary(v) for v in versions],
                             extras=[extra_from_row(e) for e in extras])


def update_application(application_id: int, update: ApplicationUpdate) -> ApplicationDetail:
    changes = update.model_dump(exclude_unset=True)
    with connect() as conn:
        row = get_row(conn, application_id)
        # Marking as applied records the date unless one is given or already set.
        if changes.get("status") == "applied" and "applied_at" not in changes and not row["applied_at"]:
            changes["applied_at"] = date.today()
        if changes:
            changes["updated_at"] = timestamp()
            columns = ", ".join(f"{k} = ?" for k in changes)
            values = [v.isoformat() if isinstance(v, date) else v for v in changes.values()]
            conn.execute(f"UPDATE applications SET {columns} WHERE id = ?", (*values, application_id))
    return get_application(application_id)


def delete_application(application_id: int) -> None:
    with connect() as conn:
        get_row(conn, application_id)
        conn.execute("DELETE FROM applications WHERE id = ?", (application_id,))


def _cv_json(cv: TailoredCV) -> str:
    return json.dumps(cv.model_dump(mode="json", by_alias=True, exclude_none=True), sort_keys=True)


def add_version(application_id: int, data: CvVersionCreate) -> CvVersion:
    """Save a CV version. If it's identical to the latest one, reuse that instead of duplicating it."""
    cv_json = _cv_json(data.cv)
    now = timestamp()
    with connect() as conn:
        get_row(conn, application_id)
        latest = conn.execute("SELECT id, cv_json FROM cv_versions WHERE application_id = ? ORDER BY id DESC LIMIT 1",
                              (application_id,)).fetchone()
        if latest and latest["cv_json"] == cv_json:
            version_id = latest["id"]
        else:
            version_id = conn.execute(
                "INSERT INTO cv_versions (application_id, label, filename, cv_json, coverage_json, suggestions_json,"
                " created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (application_id, data.label, data.cv.filename, cv_json,
                 json.dumps([c.model_dump() for c in data.coverage]),
                 json.dumps([s.model_dump() for s in data.header_extra_suggestions]), now),
            ).lastrowid
        sets = "updated_at = ?" + (", cv_version_id = ?" if data.mark_sent else "")
        params = (now, version_id) if data.mark_sent else (now,)
        conn.execute(f"UPDATE applications SET {sets} WHERE id = ?", (*params, application_id))
    return get_version(version_id)


def get_version(version_id: int) -> CvVersion:
    with connect() as conn:
        row = conn.execute("SELECT * FROM cv_versions WHERE id = ?", (version_id,)).fetchone()
    if row is None:
        raise NotFound(f"CV version {version_id} not found")
    return CvVersion(**_version_summary(row).model_dump(),
                     cv=TailoredCV.model_validate_json(row["cv_json"]),
                     coverage=json.loads(row["coverage_json"]),
                     header_extra_suggestions=json.loads(row["suggestions_json"]))
