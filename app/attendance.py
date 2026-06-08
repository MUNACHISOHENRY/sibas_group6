"""
 Attendance logic for SIBAS.

Implements the three functions specified in the Attendance_Reporting_Contract:
    get_sessions(course_id)
    mark_attendance(session_id, student_id, status)
    validate_session(session_id)

    + two supporting functions carried over from the original file:

    create_attendance_session(course_id, lecturer_id, session_date)
    get_session_attendance_report(session_id)
    get_students_for_course(course_id)

ALL database access goes through the helpers in app/db.py.
No raw psycopg2 connections are opened here.
No SQL strings are built by joining or formatting — all values are passed
as parameters to prevent SQL injection.

Valid attendance statuses (enforced at the Python layer before any DB write):
    'Present', 'Absent'

Business rules enforced here:
    BR-23/24/25 : submit_attendance_records — upsert keeps exactly one
                  record per (session, student).
    BR-19/20    : create_attendance_session — one session per course/date.
    BR-18       : get_students_for_course — only enrolled students shown.
"""






from app.db import run_query, run_query_one, run_command, run_command_returning

class AttendanceError(Exception):# Custom exception: Streamlit UI shows a friendly message
    """Raised when an attendance operation cannot be completed."""

VALID_STATUSES = {"Present", "Absent"}# Allowed status values

# CONTRACT FUNCTIONS  (required by Attendance_Reporting_Contract)

def get_sessions(course_id: int) -> list:
    """
    Retrieve all attendance sessions for a given course, most recent first.

    Parameters
    ----------
    course_id : int
        The primary key of the course in the `course` table.

    Returns
    -------
    list of dict
        Each dict has keys: session_id, course_id, lecturer_id,
        session_date, created_at, course_code, course_title,
        lecturer_name.
        Returns [] if no sessions exist or the course_id is unknown.

    Raises
    ------
    AttendanceError
        If the database query fails for any reason other than "no rows".
    """
    sql = """
        SELECT
            s.session_id,
            s.course_id,
            s.lecturer_id,
            s.session_date,
            s.created_at,
            c.course_code,
            c.course_title,
            l.full_name  AS lecturer_name
        FROM attendance_session s
        JOIN course   c ON c.course_id   = s.course_id
        JOIN lecturer l ON l.lecturer_id = s.lecturer_id
        WHERE s.course_id = %s
        ORDER BY s.session_date DESC, s.created_at DESC;
    """
    try:
        return run_query(sql, (course_id,))
    except Exception as e:
        raise AttendanceError(
            f"Could not retrieve sessions for course {course_id}: {e}"
        ) from e


def mark_attendance(session_id: int, student_id: int, status: str) -> bool:
    """
    Insert or update a student's attendance status for a session.

    Business rule 25: a student has exactly one record per session.
    An existing record is overwritten (upsert via ON CONFLICT).

    Parameters
    ----------
    session_id : int
    student_id : int
    status     : str  --  must be 'Present' or 'Absent'

    Returns
    -------
    True on success.

    Raises
    ------
    AttendanceError
        If the status value is invalid, the session does not exist,
        or the database write fails.
    """
    # 1. Validate status before touching the database.
    if status not in VALID_STATUSES:
        raise AttendanceError(
            f"Invalid status '{status}'. Allowed values: {sorted(VALID_STATUSES)}"
        )

    # 2. Confirm the session exists (contract: validate before inserting).
    if not validate_session(session_id):
        raise AttendanceError(
            f"Session {session_id} does not exist. Cannot mark attendance."
        )

    # 3. Upsert the attendance record.
    sql = """
        INSERT INTO attendance_record (session_id, student_id, status)
        VALUES (%s, %s, %s)
        ON CONFLICT (session_id, student_id)
        DO UPDATE SET status = EXCLUDED.status,
                      recorded_at = CURRENT_TIMESTAMP;
    """
    try:
        run_command(sql, (session_id, student_id, status))
        return True
    except Exception as e:
        raise AttendanceError(
            f"Failed to mark attendance for student {student_id} "
            f"in session {session_id}: {e}"
        ) from e


def validate_session(session_id: int) -> bool:
    """
    Verify that an attendance session exists in the database.

    Parameters
    ----------
    session_id : int

    Returns
    -------
    True  if the session exists.
    False if it does not exist or the query fails.
    """
    sql = "SELECT 1 FROM attendance_session WHERE session_id = %s LIMIT 1;"
    try:
        row = run_query_one(sql, (session_id,))
        return row is not None
    except Exception:
        return False


# Support Functions
def create_attendance_session(course_id: int, lecturer_id: int,
                              session_date) -> int:
    """
    Create a new attendance session for a course.

    Business rules 19 & 20: one session per course, per date, per lecturer.
    The database does not enforce a unique constraint on (course_id, session_date)
    because a lecturer could legitimately run two sessions on the same day,
    but the UI should warn if a session for that date already exists.

    Parameters
    ----------
    course_id   : int
    lecturer_id : int
    session_date: date or str  (e.g. datetime.date.today() or '2026-06-08')

    Returns
    -------
    int  --  the new session_id.

    Raises
    ------
    AttendanceError
        If the insert fails (e.g. invalid course_id or lecturer_id).
    """
    sql = """
        INSERT INTO attendance_session (course_id, lecturer_id, session_date)
        VALUES (%s, %s, %s)
        RETURNING session_id;
    """
    try:
        row = run_command_returning(sql, (course_id, lecturer_id, session_date))
        return row["session_id"]
    except Exception as e:
        raise AttendanceError(
            f"Could not create attendance session: {e}"
        ) from e


def submit_attendance_records(session_id: int, records: list) -> dict:
    """
    Bulk insert or update attendance records for a session.

    Processes every record individually so one bad row does not discard
    the rest. Returns a summary of successes and failures.

    Parameters
    ----------
    session_id : int
    records    : list of dict  --  [{'student_id': int, 'status': str}, ...]

    Returns
    -------
    dict  --  {'succeeded': int, 'failed': int, 'errors': [(student_id, msg)]}

    Raises
    ------
    AttendanceError
        If the session does not exist at all.
    """
    if not validate_session(session_id):
        raise AttendanceError(
            f"Session {session_id} not found. Cannot submit records."
        )

    summary = {"succeeded": 0, "failed": 0, "errors": []}

    for rec in records:
        sid = rec.get("student_id")
        try:
            mark_attendance(session_id, sid, rec.get("status", ""))
            summary["succeeded"] += 1
        except AttendanceError as e:
            summary["failed"] += 1
            summary["errors"].append((sid, str(e)))

    return summary


def get_students_for_course(course_id: int) -> list:
    """
    Return all students enrolled in a course.

    Business rule 18: only students registered for the course are shown
    to the lecturer when marking attendance.

    Parameters
    ----------
    course_id : int

    Returns
    -------
    list of dict
        Keys: student_id, matric_no, full_name, level.
        Returns [] on error or if no students are enrolled.
    """
    sql = """
        SELECT
            s.student_id,
            s.matric_no,
            s.full_name,
            s.level
        FROM student s
        JOIN student_course sc ON sc.student_id = s.student_id
        WHERE sc.course_id = %s
        ORDER BY s.full_name ASC;
    """
    try:
        return run_query(sql, (course_id,))
    except Exception as e:
        raise AttendanceError(
            f"Could not fetch students for course {course_id}: {e}"
        ) from e


def get_session_attendance_report(session_id: int) -> list:
    """
    Return the full attendance sheet for a completed session.

    Parameters
    ----------
    session_id : int

    Returns
    -------
    list of dict
        Keys: matric_no, full_name, status.
        Returns [] if no records exist for the session.

    Raises
    ------
    AttendanceError
        If the database query fails.
    """
    sql = """
        SELECT
            s.matric_no,
            s.full_name,
            ar.status,
            ar.recorded_at
        FROM attendance_record ar
        JOIN student s ON s.student_id = ar.student_id
        WHERE ar.session_id = %s
        ORDER BY s.full_name ASC;
    """
    try:
        return run_query(sql, (session_id,))
    except Exception as e:
        raise AttendanceError(
            f"Could not fetch attendance report for session {session_id}: {e}"
        ) from e