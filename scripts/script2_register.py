"""
script2_register.py  --  Student registration for SIBAS.

This is a named deliverable of the project (Script 2). It supports the two
registration modes required by the brief, both used by the Administrator:

  1. Individual registration  --  one student at a time
  2. Bulk registration        --  many students from a CSV upload

Per the brief: every student MUST be assigned to one or more courses at the
time of registration.

The functions defined here are imported by the Streamlit admin dashboard;
the same file can also be run from the command line for testing:

    # Bulk import from a CSV
    python scripts/script2_register.py --csv data/sample_students.csv

    # Single demo registration (uses values from data/test_setup.sql)
    python scripts/script2_register.py --demo


CSV FORMAT
----------
Required header row, columns can be in any order:

    matric_no, full_name, email, programme, level, username, password, courses

  - 'programme' is the programme NAME (e.g. "BSc Computer Science"),
    NOT the id. The programme must already exist in the database.
  - 'level' must be one of 100, 200, 300, 400, 500.
  - 'courses' is a SEMICOLON-separated list of course CODES
    (e.g. "DTS304;CSC310"). Each course must already exist in the database.


SECURITY
--------
  - Passwords are hashed with bcrypt before being stored (never plain text).
  - Every database write uses parameterised queries -- no string concatenation,
    no SQL injection possible.
  - Each student registration is wrapped in a transaction: if any step
    fails (duplicate matric, missing course, etc.), nothing for that
    student is saved.
"""

import argparse
import csv
import sys
from io import StringIO
from pathlib import Path

# Make the project root importable so 'from app.db import ...' works
# when this script is run directly from the command line.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import bcrypt
from app.db import get_connection


# --------------------------------------------------------------------------- #
# Constants & small helpers
# --------------------------------------------------------------------------- #

VALID_LEVELS = {100, 200, 300, 400, 500}

REQUIRED_CSV_COLUMNS = [
    "matric_no", "full_name", "email",
    "programme", "level", "username", "password", "courses",
]


def _hash_password(plain_password: str) -> str:
    """Hash a password with bcrypt. The salt is included in the output."""
    return bcrypt.hashpw(plain_password.encode(), bcrypt.gensalt(rounds=12)).decode()


def _lookup_programme_id(cur, programme_name: str):
    """Return programme_id for a given programme name, or None if not found."""
    cur.execute(
        "SELECT programme_id FROM programme WHERE programme_name = %s",
        (programme_name,),
    )
    row = cur.fetchone()
    return row[0] if row else None


def _lookup_course_id(cur, course_code: str):
    """Return course_id for a given course code, or None if not found."""
    cur.execute(
        "SELECT course_id FROM course WHERE course_code = %s",
        (course_code,),
    )
    row = cur.fetchone()
    return row[0] if row else None


def _validate_inputs(matric_no, full_name, email, programme, level,
                     username, password, courses):
    """Basic input checks. Returns a list of error strings (empty list = OK)."""
    errors = []

    if not matric_no or not str(matric_no).strip():
        errors.append("matric_no is required")
    if not full_name or not str(full_name).strip():
        errors.append("full_name is required")
    if not email or "@" not in str(email):
        errors.append("email looks invalid")
    if not programme or not str(programme).strip():
        errors.append("programme is required")

    try:
        if int(level) not in VALID_LEVELS:
            errors.append(f"level must be one of {sorted(VALID_LEVELS)}")
    except (ValueError, TypeError):
        errors.append("level must be a number")

    if not username or not str(username).strip():
        errors.append("username is required")
    if not password or len(str(password)) < 6:
        errors.append("password must be at least 6 characters")
    if not courses or len(courses) == 0:
        errors.append("at least one course is required")

    return errors


# --------------------------------------------------------------------------- #
# Core: register a single student (used by both individual and bulk flows)
# --------------------------------------------------------------------------- #

def register_student(
    matric_no: str,
    full_name: str,
    email: str,
    programme_name: str,
    level,
    username: str,
    password: str,
    course_codes: list,
) -> dict:
    """
    Register ONE student and enroll them into one or more courses, atomically.

    Returns:
        {"ok": True,  "student_id": <int>}    on success
        {"ok": False, "error": "<message>"}   on failure
    """
    # 1. Validate before touching the database.
    errs = _validate_inputs(
        matric_no, full_name, email, programme_name, level,
        username, password, course_codes,
    )
    if errs:
        return {"ok": False, "error": "; ".join(errs)}

    conn = get_connection()
    try:
        with conn.cursor() as cur:

            # 2. Resolve programme name -> id.
            programme_id = _lookup_programme_id(cur, programme_name.strip())
            if programme_id is None:
                conn.rollback()
                return {"ok": False, "error": f"programme '{programme_name}' not found"}

            # 3. Resolve every course code -> id (fail fast if any unknown).
            course_ids = []
            for code in course_codes:
                cid = _lookup_course_id(cur, code.strip())
                if cid is None:
                    conn.rollback()
                    return {"ok": False, "error": f"course code '{code}' not found"}
                course_ids.append(cid)

            # 4. Create the login account.
            cur.execute(
                """
                INSERT INTO app_user (username, password_hash, role, status)
                VALUES (%s, %s, 'Student', 'active')
                RETURNING user_id
                """,
                (username.strip(), _hash_password(password)),
            )
            user_id = cur.fetchone()[0]

            # 5. Create the student record.
            cur.execute(
                """
                INSERT INTO student
                    (matric_no, full_name, email, programme_id, user_id, level)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING student_id
                """,
                (
                    matric_no.strip(),
                    full_name.strip(),
                    email.strip(),
                    programme_id,
                    user_id,
                    int(level),
                ),
            )
            student_id = cur.fetchone()[0]

            # 6. Enroll into every course.
            for cid in course_ids:
                cur.execute(
                    "INSERT INTO student_course (student_id, course_id) VALUES (%s, %s)",
                    (student_id, cid),
                )

        # All inserts succeeded -- commit as one transaction.
        conn.commit()
        return {"ok": True, "student_id": student_id}

    except Exception as e:
        # Any failure (duplicate matric, duplicate email, duplicate username,
        # FK violation, etc.) rolls back the whole student registration so
        # we never leave half-created records.
        conn.rollback()
        return {"ok": False, "error": str(e)}
    finally:
        conn.close()


# --------------------------------------------------------------------------- #
# Bulk: register many students from a CSV
# --------------------------------------------------------------------------- #

def register_students_from_csv(csv_source) -> dict:
    """
    Read a CSV of students and register each row.

    csv_source can be:
      - a path string to a .csv file on disk, OR
      - a file-like object (e.g. a Streamlit UploadedFile).

    Each row is its own transaction: a single bad row does NOT roll back
    earlier good rows.

    Returns:
        {
          "total":     <int>,
          "succeeded": <int>,
          "failed":    <int>,
          "errors":    [(row_number, error_message), ...],
        }
    """
    summary = {"total": 0, "succeeded": 0, "failed": 0, "errors": []}

    # Accept either a path or an uploaded file object.
    opened_here = False
    if hasattr(csv_source, "read"):
        text = csv_source.read()
        if isinstance(text, bytes):
            text = text.decode("utf-8")
        file_obj = StringIO(text)
    else:
        file_obj = open(csv_source, newline="", encoding="utf-8")
        opened_here = True

    try:
        reader = csv.DictReader(file_obj)

        # Verify header has every required column.
        missing = [c for c in REQUIRED_CSV_COLUMNS
                   if c not in (reader.fieldnames or [])]
        if missing:
            summary["errors"].append((0, f"CSV missing columns: {missing}"))
            return summary

        # Row 1 is the header, so data rows start at line 2.
        for line_num, row in enumerate(reader, start=2):
            summary["total"] += 1

            # Parse 'courses' as semicolon-separated list of course codes.
            courses_raw = (row.get("courses") or "").strip()
            course_codes = [c.strip() for c in courses_raw.split(";") if c.strip()]

            result = register_student(
                matric_no      = row.get("matric_no", ""),
                full_name      = row.get("full_name", ""),
                email          = row.get("email", ""),
                programme_name = row.get("programme", ""),
                level          = row.get("level", ""),
                username       = row.get("username", ""),
                password       = row.get("password", ""),
                course_codes   = course_codes,
            )

            if result["ok"]:
                summary["succeeded"] += 1
            else:
                summary["failed"] += 1
                summary["errors"].append((line_num, result["error"]))

    finally:
        if opened_here:
            file_obj.close()

    return summary


# --------------------------------------------------------------------------- #
# Command-line entry point  (so you can test this script directly)
# --------------------------------------------------------------------------- #

def _cli():
    parser = argparse.ArgumentParser(
        description="Register students into SIBAS individually or in bulk.",
    )
    parser.add_argument(
        "--csv",
        help="Path to a CSV file of students to register in bulk.",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run a built-in demo registration (uses values from data/test_setup.sql).",
    )
    args = parser.parse_args()

    if args.csv:
        print(f"Registering students from: {args.csv}\n")
        summary = register_students_from_csv(args.csv)
        print(f"Total rows attempted : {summary['total']}")
        print(f"Succeeded            : {summary['succeeded']}")
        print(f"Failed               : {summary['failed']}")
        if summary["errors"]:
            print("\nErrors:")
            for line_num, msg in summary["errors"]:
                print(f"  line {line_num}: {msg}")
        return

    if args.demo:
        print("Running demo registration ...")
        result = register_student(
            matric_no      = "CSC/2023/999",
            full_name      = "Demo Student",
            email          = "demo.student@pau.edu.ng",
            programme_name = "BSc Computer Science",
            level          = 300,
            username       = "demo.student",
            password       = "Demo123!",
            course_codes   = ["DTS304"],
        )
        print(result)
        return

    parser.print_help()


if __name__ == "__main__":
    _cli()
