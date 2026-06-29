"""
app/reports.py  --  Reporting & threshold logic for SIBAS.

Every report shown in the app comes from this module. The shape we return
is intentionally simple so the dashboards can paint it with one or two
lines of code.

Rules respected throughout this file:
    * All DB access goes through app/db.py (no raw psycopg2 connections,
      no pd.read_sql).
    * Every SQL string is parameterised. No f-strings, no string
      concatenation, no values injected into the query text.
    * Schema is treated as 3NF: a student's department is reached via
      student -> programme -> department. There is no department_id
      column on `student`.
    * The 80% attendance threshold is read from the `system_setting`
      table (single row, setting_id = 1). The admin can change it from
      the Configuration page; every report picks up the new value the
      next time it runs.

Functions exposed to the dashboards:
    Threshold:
        get_threshold()              -> float
        update_threshold(new_value)  -> float (the new value)

    Student-facing:
        get_student_profile(user_id)       -> dict
        get_student_attendance(student_id) -> list of per-course dicts

    Generic report:
        generate_report(department=None,
                        course_id=None,
                        course_code=None,
                        level=None,
                        lecturer_id=None) -> list of dicts

    Convenience filters over an already-fetched list:
        generate_student_report(rows, matric_no)
        generate_course_report(rows, course_code)
        generate_department_report(rows, department)

    Exports:
        export_csv(rows)             -> bytes  (admin/lecturer Download button)
        export_to_csv(rows)          -> bytes  (alias kept for backwards-compat)
        export_to_pdf(rows, title)   -> BytesIO

A "row" in this module is a dict with the following keys:
    matric_no, full_name, department, programme, level,
    course_code, course_title, total_sessions, sessions_present,
    attendance_percent, eligible    ('Yes' / 'No')
"""

from io import BytesIO, StringIO
import csv

from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet

from app.db import run_query, run_query_one, run_command


# ---------------------------------------------------------------------------
# Threshold (system_setting)
# ---------------------------------------------------------------------------
#
# system_setting is a single-row table. We always read/update setting_id = 1.
# attendance_threshold is NUMERIC(5,2) in PostgreSQL, which psycopg2 returns
# as a Python Decimal. We convert to float so Streamlit's number widgets and
# comparisons (pct >= threshold) work without surprises.

def get_threshold() -> float:
    """Return the current attendance threshold as a float (e.g. 80.0)."""
    row = run_query_one(
        "SELECT attendance_threshold FROM system_setting WHERE setting_id = 1;"
    )
    if row is None:
        # Defensive fallback. Script 1 always seeds a row, so we should
        # never hit this in practice -- but a missing setting shouldn't
        # crash the whole app.
        return 80.0
    return float(row["attendance_threshold"])


def update_threshold(new_value) -> float:
    """
    Update the attendance threshold and return the value that was stored.

    The CHECK constraint on the column already enforces 0 <= value <= 100,
    but we check here too so we can raise a friendlier error than a raw
    psycopg2 IntegrityError.
    """
    value = float(new_value)
    if value < 0 or value > 100:
        raise ValueError("Threshold must be between 0 and 100 (percent).")

    run_command(
        """
        UPDATE system_setting
        SET    attendance_threshold = %s,
               updated_at           = CURRENT_TIMESTAMP
        WHERE  setting_id = 1;
        """,
        (value,),
    )
    return value


# ---------------------------------------------------------------------------
# Student-facing helpers
# ---------------------------------------------------------------------------
#
# The student dashboard shows the logged-in student's own data. The session
# only knows their user_id (set at login), so we have to translate that to
# a student_id and pull profile fields from the related tables.

def get_student_profile(user_id: int) -> dict | None:
    """
    Return the profile of the student who owns this app_user account.

    Shape:
        {
            "student_id":     int,
            "matric_no":      str,   (dashboards may also read "matric_number")
            "matric_number":  str,   (alias kept for the existing UI)
            "full_name":      str,
            "email":          str,
            "level":          int,
            "programme":      str,
            "department":     str,
        }
    Returns None if the user_id doesn't belong to a student.
    """
    row = run_query_one(
        """
        SELECT
            s.student_id,
            s.matric_no,
            s.full_name,
            s.email,
            s.level,
            p.programme_name AS programme,
            d.department_name AS department
        FROM student s
        JOIN programme  p ON p.programme_id  = s.programme_id
        JOIN department d ON d.department_id = p.department_id
        WHERE s.user_id = %s;
        """,
        (user_id,),
    )
    if row is None:
        return None

    # The frontend was written against "matric_number"; expose both so
    # neither half of the code has to change.
    row["matric_number"] = row["matric_no"]
    return row


def get_student_attendance(student_id: int) -> list:
    """
    Return per-course attendance totals for one student.

    Each item:
        {
            "course_id":     int,
            "course_code":   str,
            "course_title":  str,
            "title":         str,   (alias for the dashboard)
            "total":         int,   (total sessions for that course)
            "present":       int,   (sessions the student was Present in)
        }

    We count ALL sessions of every course the student is enrolled in --
    not just the ones they happen to have a record for. A missing
    attendance_record row counts as zero presents, which is the correct
    behaviour (a student who skipped class shouldn't have their %
    calculated against a smaller denominator).
    """
    rows = run_query(
        """
        SELECT
            c.course_id,
            c.course_code,
            c.course_title,
            COUNT(DISTINCT ses.session_id) AS total,
            COUNT(
                DISTINCT CASE
                    WHEN ar.status = 'Present' THEN ses.session_id
                END
            ) AS present
        FROM student_course sc
        JOIN course c
            ON c.course_id = sc.course_id
        LEFT JOIN attendance_session ses
            ON ses.course_id = c.course_id
        LEFT JOIN attendance_record ar
            ON  ar.session_id = ses.session_id
            AND ar.student_id = sc.student_id
        WHERE sc.student_id = %s
        GROUP BY c.course_id, c.course_code, c.course_title
        ORDER BY c.course_code;
        """,
        (student_id,),
    )

    # Add the "title" alias that the dashboard expects.
    for r in rows:
        r["title"] = r["course_title"]
        r["total"] = int(r["total"])
        r["present"] = int(r["present"])

    return rows


# ---------------------------------------------------------------------------
# Generic report  (used by both admin and lecturer dashboards)
# ---------------------------------------------------------------------------
#
# This is the workhorse. It produces one row per (student, course) combination
# and supports optional filters. All filters are passed as parameters; never
# spliced into the SQL string.
#
# A note on the filters:
#   - `course_id` (int) and `course_code` (str) are interchangeable. The
#     lecturer dashboard sends a course code; the admin dashboard sends an
#     id. Whichever one is given is the one we filter on.
#   - `lecturer_id` lets us limit reports to a specific lecturer's courses
#     (used by the lecturer's "my reports" tab).

def _fetch_attendance_rows(
    department=None,
    course_id=None,
    course_code=None,
    level=None,
    lecturer_id=None,
) -> list:
    """
    Internal: build the parameterised report query and run it.

    We build the WHERE clause by appending strings only from a fixed set of
    known-safe predicates -- never from user input. The user's values are
    always passed as bound parameters in `params`.
    """
    where_parts = []
    params = []

    if department is not None:
        where_parts.append("d.department_name = %s")
        params.append(department)

    if course_id is not None:
        where_parts.append("c.course_id = %s")
        params.append(int(course_id))

    if course_code is not None:
        where_parts.append("c.course_code = %s")
        params.append(course_code)

    if level is not None:
        where_parts.append("s.level = %s")
        params.append(int(level))

    if lecturer_id is not None:
        where_parts.append("c.lecturer_id = %s")
        params.append(int(lecturer_id))

    where_clause = ("WHERE " + " AND ".join(where_parts)) if where_parts else ""

    # SQL template. The only placeholder is {where_clause} which is
    # filled from `where_parts` -- a list of hardcoded predicate strings
    # like "d.department_name = %s" built above. NO user value is ever
    # spliced into the SQL text. Every user value flows through `params`
    # and is bound by psycopg2.
    sql_template = (
        "SELECT "
        "    s.matric_no, "
        "    s.full_name, "
        "    d.department_name  AS department, "
        "    p.programme_name   AS programme, "
        "    s.level, "
        "    c.course_id, "
        "    c.course_code, "
        "    c.course_title, "
        "    COUNT(DISTINCT ses.session_id) AS total_sessions, "
        "    COUNT(DISTINCT CASE WHEN ar.status = 'Present' "
        "                       THEN ses.session_id END) AS sessions_present "
        "FROM student s "
        "JOIN programme  p  ON p.programme_id  = s.programme_id "
        "JOIN department d  ON d.department_id = p.department_id "
        "JOIN student_course sc ON sc.student_id = s.student_id "
        "JOIN course     c  ON c.course_id     = sc.course_id "
        "LEFT JOIN attendance_session ses "
        "    ON ses.course_id = c.course_id "
        "LEFT JOIN attendance_record ar "
        "    ON  ar.session_id = ses.session_id "
        "    AND ar.student_id = s.student_id "
        "{where_clause} "
        "GROUP BY "
        "    s.matric_no, s.full_name, d.department_name, p.programme_name, "
        "    s.level, c.course_id, c.course_code, c.course_title "
        "ORDER BY d.department_name, c.course_code, s.full_name;"
    )
    sql = sql_template.format(where_clause=where_clause)
    return run_query(sql, tuple(params) if params else None)


def generate_report(
    department=None,
    course_id=None,
    course_code=None,
    level=None,
    lecturer_id=None,
    threshold=None,
) -> list:
    """
    Unified report function used by every dashboard.

    Returns a list of dicts; each dict represents one (student, course)
    combination with totals, attendance percent and an eligibility flag.

    All filters are optional. If `threshold` is not supplied, we read the
    current value from system_setting.
    """
    rows = _fetch_attendance_rows(
        department=department,
        course_id=course_id,
        course_code=course_code,
        level=level,
        lecturer_id=lecturer_id,
    )

    if threshold is None:
        threshold = get_threshold()

    for r in rows:
        total = int(r["total_sessions"])
        present = int(r["sessions_present"])
        # Edge case: a course with no sessions yet (e.g. start of term).
        # A student who has had no chance to miss class is NOT ineligible,
        # so we report 100%. This matches the student dashboard's rule and
        # avoids the day-1-of-semester case where every student would
        # otherwise be flagged.
        pct = (present / total * 100) if total > 0 else 100.0
        r["total_sessions"] = total
        r["sessions_present"] = present
        r["attendance_percent"] = round(pct, 2)
        # Both keys are present so either dashboard works without reshaping.
        r["eligible"] = "Yes" if pct >= threshold else "No"
        r["status"] = "Eligible" if pct >= threshold else "Ineligible"

    return rows


# ---------------------------------------------------------------------------
# Filters over an already-fetched list
# ---------------------------------------------------------------------------
#
# These are kept from the original module for backwards compatibility.
# They no longer take a pandas DataFrame -- they operate on the list of
# dicts that generate_report returns.

def generate_student_report(rows: list, matric_no: str) -> list:
    return [r for r in rows if r.get("matric_no") == matric_no]


def generate_course_report(rows: list, course_code: str) -> list:
    return [r for r in rows if r.get("course_code") == course_code]


def generate_department_report(rows: list, department: str) -> list:
    return [r for r in rows if r.get("department") == department]


# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------

# A fixed column order so every export looks the same and downstream
# parsers don't have to guess.
_EXPORT_COLUMNS = [
    "matric_no", "full_name", "department", "programme", "level",
    "course_code", "course_title",
    "total_sessions", "sessions_present", "attendance_percent",
    "eligible",
]


def export_to_csv(rows: list) -> bytes:
    """
    Serialise report rows to CSV bytes (UTF-8). Used by Streamlit's
    st.download_button.
    """
    buf = StringIO()
    writer = csv.DictWriter(buf, fieldnames=_EXPORT_COLUMNS, extrasaction="ignore")
    writer.writeheader()
    for r in rows:
        writer.writerow(r)
    return buf.getvalue().encode("utf-8")


# The dashboards call this name. Kept as an alias rather than renaming the
# original so older code/tests continue to work.
def export_csv(rows: list) -> bytes:
    return export_to_csv(rows)


def export_to_pdf(rows: list, title: str = "Attendance Report") -> BytesIO:
    """
    Render report rows to a PDF and return it as an in-memory BytesIO.
    The caller passes the bytes to st.download_button.
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)

    styles = getSampleStyleSheet()
    elements = [Paragraph(title, styles["Title"])]

    header = _EXPORT_COLUMNS
    data = [header] + [
        [str(r.get(col, "")) for col in header] for r in rows
    ]

    table = Table(data, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
        ("TEXTCOLOR",  (0, 0), (-1, 0), colors.white),
        ("GRID",       (0, 0), (-1, -1), 0.5, colors.black),
        ("ALIGN",      (0, 0), (-1, -1), "CENTER"),
        ("FONTSIZE",   (0, 0), (-1, -1), 7),
    ]))

    elements.append(table)
    doc.build(elements)
    buffer.seek(0)
    return buffer
