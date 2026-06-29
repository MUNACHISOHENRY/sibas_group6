"""
app/api.py  --  Frontend-facing adapter layer for SIBAS.

WHY THIS FILE EXISTS
--------------------
The frontend (the Streamlit dashboards) was written against a slightly
different set of function names and field names than the real backend
modules (auth.py, attendance.py, reports.py). Rather than rewrite either
side, we sit a thin adapter in the middle:

    Dashboards  -->  app/api.py  -->  app/auth.py
                                  -->  app/attendance.py
                                  -->  app/reports.py
                                  -->  app/db.py  (direct, for tiny lookups)

Every function in this file does at most one of:
    - rename a function (`create_session` -> `create_attendance_session`)
    - reshape a return value (`status` -> `is_active`, `course_title` -> `title`)
    - combine two backend calls into one (CSV row -> matric -> student_id ->
      mark_attendance)

There is NO business logic in here. If you find yourself writing a SQL
JOIN or a validation rule in this file, it belongs in one of the backend
modules instead.

SECURITY
--------
This file talks to the database only through `run_query` / `run_command`
from app/db.py, and only with parameterised values. No raw psycopg2,
no f-strings inside SQL.
"""

import csv
from io import StringIO

import bcrypt

from app.db import run_query, run_query_one, run_command
from app import attendance as _attendance


# ===========================================================================
# 1.  AUTHENTICATION & USER MANAGEMENT
# ===========================================================================
#
# These functions were previously in app/auth_wrapper.py. They are inlined
# here so the dashboards have one import to learn.

def hash_password(password: str) -> str:
    return bcrypt.hashpw(
        password.encode("utf-8"), bcrypt.gensalt()
    ).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(
        password.encode("utf-8"), hashed.encode("utf-8")
    )


def authenticate(username, password):
    """
    Verify a username/password against app_user.

    Returns {"user_id": int, "role": str} on success, None on failure.
    The shape is what the login screen expects -- it stores user_id and
    role in st.session_state and never touches the password hash again.
    """
    user = run_query_one(
        """
        SELECT user_id, password_hash, role, status
        FROM   app_user
        WHERE  username = %s
        """,
        (username,),
    )
    if user is None:
        return None
    if user["status"] != "active":
        return None
    if not verify_password(password, user["password_hash"]):
        return None
    return {"user_id": user["user_id"], "role": user["role"]}


def get_all_users():
    """
    Return every user as the dashboard expects:
        {"user_id", "username", "role", "is_active"}

    Internally we store status as 'active'/'inactive'. The frontend wants
    a boolean, so we translate at this boundary and nowhere else.
    """
    rows = run_query(
        "SELECT user_id, username, role, status FROM app_user ORDER BY user_id"
    )
    return [
        {
            "user_id":   r["user_id"],
            "username":  r["username"],
            "role":      r["role"],
            "is_active": r["status"] == "active",
        }
        for r in rows
    ]


def create_user(username, password, role, is_active=True, full_name=None, email=None):
    """
    Create an app_user row and, for Lecturer role, the matching lecturer row.

    Lecturer accounts require full_name and email so the lecturer table
    (which the rest of the system queries) gets a complete record.
    Both inserts run in a single transaction -- if the lecturer insert fails
    the app_user row is rolled back too.
    """
    if role not in ("Administrator", "Lecturer", "Student"):
        raise ValueError("Invalid role.")
    if role == "Lecturer":
        if not full_name or not str(full_name).strip():
            raise ValueError("Full name is required for Lecturer accounts.")
        if not email or "@" not in str(email):
            raise ValueError("A valid email is required for Lecturer accounts.")

    from app.db import get_connection
    status = "active" if is_active else "inactive"
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO app_user (username, password_hash, role, status)
                VALUES (%s, %s, %s, %s)
                RETURNING user_id
                """,
                (username, hash_password(password), role, status),
            )
            user_id = cur.fetchone()[0]

            if role == "Lecturer":
                cur.execute(
                    """
                    INSERT INTO lecturer (full_name, email, user_id)
                    VALUES (%s, %s, %s)
                    """,
                    (full_name.strip(), email.strip(), user_id),
                )
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def deactivate_user(user_id):
    run_command(
        "UPDATE app_user SET status = 'inactive' WHERE user_id = %s",
        (user_id,),
    )
    return True


def delete_user(user_id):
    """
    Delete an app_user. ON DELETE CASCADE in the schema means the linked
    student / lecturer / administrator row is removed too.
    """
    run_command("DELETE FROM app_user WHERE user_id = %s", (user_id,))
    return True


# ---------------------------------------------------------------------------
# Admin "Update User" actions  (brief: "create, update, deactivate, delete")
# ---------------------------------------------------------------------------
# Each function does exactly one thing and validates its own inputs. The
# admin UI exposes them through a single "Update User" form with an action
# dropdown that routes to the right one.

def reset_user_password(user_id, new_password):
    """Replace the user's password hash. Min 6 chars."""
    if not new_password or len(new_password) < 6:
        raise ValueError("New password must be at least 6 characters.")
    run_command(
        "UPDATE app_user SET password_hash = %s WHERE user_id = %s",
        (hash_password(new_password), user_id),
    )
    return True


def update_user_role(user_id, new_role):
    """
    Change a user's role. The CHECK constraint on the column already
    enforces the allowed values, but we re-check here so the UI gets a
    friendlier error than a raw IntegrityError.

    NOTE: changing role does NOT create a matching student/lecturer/
    administrator row; that has to be done separately. Use with care.
    """
    if new_role not in ("Administrator", "Lecturer", "Student"):
        raise ValueError("Invalid role.")
    run_command(
        "UPDATE app_user SET role = %s WHERE user_id = %s",
        (new_role, user_id),
    )
    return True


def reactivate_user(user_id):
    """Flip an inactive account back to active. Completes the lifecycle
    so deactivate isn't a one-way door."""
    run_command(
        "UPDATE app_user SET status = 'active' WHERE user_id = %s",
        (user_id,),
    )
    return True


def rename_user(user_id, new_username):
    """Change the login name. UNIQUE constraint on username will reject
    a clash with a friendlier-looking error via the caller's try/except."""
    if not new_username or not new_username.strip():
        raise ValueError("Username is required.")
    run_command(
        "UPDATE app_user SET username = %s WHERE user_id = %s",
        (new_username.strip(), user_id),
    )
    return True


def get_lecturer_id_from_user_id(user_id):
    """Map a logged-in lecturer's user_id to their lecturer_id."""
    row = run_query_one(
        "SELECT lecturer_id FROM lecturer WHERE user_id = %s",
        (user_id,),
    )
    return row["lecturer_id"] if row else None


# ===========================================================================
# 2.  LECTURER WORKFLOW  (sessions, attendance, override)
# ===========================================================================
#
# These names match what the lecturer dashboard already imports. Under
# the hood we delegate to attendance.py wherever possible, only writing
# raw queries when attendance.py doesn't already cover the case.

def get_assigned_courses(lecturer_id: int) -> list:
    """
    Courses taught by this lecturer.

    Shape expected by the UI:
        [{"course_id", "course_code", "course_title", "title"}, ...]

    The dashboard reads c["title"] in some places and c["course_title"] in
    others. We expose both so neither needs to change.
    """
    rows = run_query(
        """
        SELECT course_id, course_code, course_title
        FROM   course
        WHERE  lecturer_id = %s
        ORDER  BY course_code
        """,
        (lecturer_id,),
    )
    for r in rows:
        r["title"] = r["course_title"]
    return rows


def create_session(lecturer_id, course_id, date):
    """
    Create a new attendance session.

    Per BR-19/20 a session represents one course on one date. The schema
    does not store start_time / end_time; the UI no longer collects them.
    Returns the new session_id.
    """
    return _attendance.create_attendance_session(
        course_id=course_id,
        lecturer_id=lecturer_id,
        session_date=date,
    )


def get_students_for_session(session_id: int) -> list:
    """
    Enrolled students for the course this session belongs to.

    Used by the override page so a lecturer can correct (or add) the
    status of ANY enrolled student, not only those who already have a
    record. We resolve session -> course internally to keep the UI thin.
    """
    sess = run_query_one(
        "SELECT course_id FROM attendance_session WHERE session_id = %s",
        (session_id,),
    )
    if sess is None:
        return []
    return _attendance.get_students_for_course(sess["course_id"])


def get_my_sessions(lecturer_id: int) -> list:
    """
    All sessions created by this lecturer, newest first.

    Shape expected by the UI:
        session_id, course_id, course_code, session_date
    """
    return run_query(
        """
        SELECT
            ses.session_id,
            ses.course_id,
            ses.session_date,
            ses.created_at,
            c.course_code,
            c.course_title
        FROM   attendance_session ses
        JOIN   course c ON c.course_id = ses.course_id
        WHERE  ses.lecturer_id = %s
        ORDER  BY ses.session_date DESC, ses.created_at DESC
        """,
        (lecturer_id,),
    )


def upload_attendance(session_id: int, csv_source) -> dict:
    """
    Bulk-record attendance for a session from a CSV upload.

    Required CSV columns: matric_no, status
        (we also accept 'matric_number' as an alias for matric_no in case
        an older CSV is still around)
        status must be 'Present' or 'Absent'

    Returns:
        {"success": int, "errors": [(matric_no, message), ...]}
    """
    # Accept either a Streamlit UploadedFile or a path string.
    if hasattr(csv_source, "read"):
        # Reset to start in case the dashboard read it for preview already.
        try:
            csv_source.seek(0)
        except Exception:
            pass
        text = csv_source.read()
        if isinstance(text, bytes):
            text = text.decode("utf-8")
        file_obj = StringIO(text)
        opened_here = False
    else:
        file_obj = open(csv_source, newline="", encoding="utf-8")
        opened_here = True

    summary = {"success": 0, "errors": []}

    try:
        reader = csv.DictReader(file_obj)
        for row in reader:
            matric = (row.get("matric_no")
                      or row.get("matric_number") or "").strip()
            status = (row.get("status") or "").strip()

            if not matric:
                summary["errors"].append(("", "missing matric_no"))
                continue

            # Resolve matric -> student_id.
            student = run_query_one(
                "SELECT student_id FROM student WHERE matric_no = %s",
                (matric,),
            )
            if student is None:
                summary["errors"].append((matric, "matric_no not found"))
                continue

            try:
                _attendance.mark_attendance(
                    session_id=session_id,
                    student_id=student["student_id"],
                    status=status,
                )
                summary["success"] += 1
            except _attendance.AttendanceError as e:
                summary["errors"].append((matric, str(e)))
    finally:
        if opened_here:
            file_obj.close()

    return summary


def get_session_records(session_id: int) -> list:
    """
    Per-student records for one session, used by the override page.

    The schema's PK on attendance_record is `attendance_id`. The dashboard
    refers to it as record_id, so we expose both.
    """
    rows = run_query(
        """
        SELECT
            ar.attendance_id,
            ar.session_id,
            ar.student_id,
            ar.status,
            ar.recorded_at,
            s.matric_no,
            s.full_name
        FROM   attendance_record ar
        JOIN   student s ON s.student_id = ar.student_id
        WHERE  ar.session_id = %s
        ORDER  BY s.full_name
        """,
        (session_id,),
    )
    for r in rows:
        r["record_id"] = r["attendance_id"]
    return rows


def override_attendance(session_id: int, student_id: int, new_status: str) -> bool:
    """
    Set (or correct) a student's status for one session.

    This is the canonical write path for individual attendance changes.
    It delegates to attendance.mark_attendance, which uses ON CONFLICT
    upsert semantics:
        - if no record exists yet for (session, student) -> INSERT
        - if a record already exists                     -> UPDATE
    So the same form handles both "fix a mistake" and "add a missing row".
    The CSV upload uses exactly the same backend call, so there is one
    write path to defend.
    """
    if new_status not in ("Present", "Absent"):
        raise ValueError("status must be 'Present' or 'Absent'")

    _attendance.mark_attendance(
        session_id=session_id,
        student_id=student_id,
        status=new_status,
    )
    return True

