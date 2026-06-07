"""
db.py — Shared database access layer for SIBAS.

EVERY part of the app talks to PostgreSQL through this file.
Do NOT write raw SQL anywhere else, and NEVER build queries by joining
strings together (that allows SQL injection). Always pass values through
the `params` argument — psycopg2 fills them in safely.

Quick reference:
    from app.db import run_query, run_query_one, run_command, run_command_returning

    # SELECT many rows (returns a list; each row is a dict)
    students = run_query("SELECT * FROM student WHERE level = %s", (300,))

    # SELECT one row (returns a dict, or None)
    s = run_query_one("SELECT * FROM student WHERE matric_number = %s", ("CSC/21/001",))

    # INSERT / UPDATE / DELETE (returns number of rows affected)
    run_command(
        "UPDATE student SET email = %s WHERE student_id = %s",
        ("new@pau.edu.ng", 5),
    )

    # INSERT and get the new id back
    row = run_command_returning(
        "INSERT INTO student (full_name) VALUES (%s) RETURNING student_id",
        ("Jane Doe",),
    )
    new_id = row["student_id"]

IMPORTANT: the %s above are placeholders, NOT Python string formatting.
Never do  f"... WHERE id = {user_input}"  — always pass values as params.
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

# Load DB credentials from the .env file. Never hard-code passwords here.
load_dotenv()


def get_connection():
    """Open a new connection to PostgreSQL using the values in .env."""
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432"),
        dbname=os.getenv("DB_NAME", "sibas"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", ""),
    )


def run_query(sql, params=None):
    """
    Run a SELECT and return ALL matching rows.

    sql    : SQL text with %s placeholders for any values
    params : tuple/list of values for those placeholders (passed safely)

    Returns: list of rows, where each row is a dict {column_name: value}
    """
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, params)
            return cur.fetchall()
    finally:
        conn.close()


def run_query_one(sql, params=None):
    """Like run_query, but returns only the FIRST row (or None if no match)."""
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, params)
            return cur.fetchone()
    finally:
        conn.close()


def run_command(sql, params=None):
    """
    Run an INSERT, UPDATE, or DELETE.

    Commits the change. If anything goes wrong it rolls back so the
    database is never left half-changed.

    Returns: number of rows affected.
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            conn.commit()
            return cur.rowcount
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def run_command_returning(sql, params=None):
    """
    Run an INSERT/UPDATE that ends with 'RETURNING ...' to get a value back
    (most often the new row's id).

    Returns: the first returned row as a dict.
    """
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, params)
            result = cur.fetchone()
            conn.commit()
            return result
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# Run  `python app/db.py`  from the project root to test the connection.
if __name__ == "__main__":
    try:
        rows = run_query("SELECT version();")
        print("Connected to PostgreSQL successfully.")
        print(rows[0]["version"])
    except Exception as e:
        print("Could NOT connect to the database.")
        print("Check that:")
        print("  1. PostgreSQL is running")
        print("  2. You created a .env file (copy it from .env.example)")
        print("  3. The values in .env match your local PostgreSQL setup")
        print("Error detail:", e)