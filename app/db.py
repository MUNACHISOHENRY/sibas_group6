"""
db.py — Shared database access layer for SIBAS.

EVERY part of the app talks to PostgreSQL through this file.
Do NOT write raw SQL anywhere else, and NEVER build queries by joining
strings together (that allows SQL injection). Always pass values through
the `params` argument — psycopg2 fills them in safely.
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

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
    Returns a list of dictionaries.
    """
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, params)
            return cur.fetchall()
    finally:
        conn.close()


def run_query_one(sql, params=None):
    """
    Run a SELECT and return only the first row.
    Returns a dictionary or None.
    """
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, params)
            return cur.fetchone()
    finally:
        conn.close()


def run_command(sql, params=None):
    """
    Run INSERT, UPDATE, DELETE.
    Returns number of rows affected.
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
    Run INSERT/UPDATE with RETURNING clause.
    Returns first returned row as dictionary.
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


# ------------------------------------------------------------------
# Compatibility helper for older modules.
# SELECT -> returns rows
# INSERT/UPDATE/DELETE -> returns affected row count
# ------------------------------------------------------------------
def execute_query(sql, params=None):
    command = sql.strip().upper()

    if command.startswith("SELECT"):
        return run_query(sql, params)

    return run_command(sql, params)


if __name__ == "__main__":
    try:
        rows = run_query("SELECT version();")
        print("Connected to PostgreSQL successfully.")
        print(rows[0]["version"])
    except Exception as e:
        print("Could NOT connect to the database.")
        print("Check that:")
        print("  1. PostgreSQL is running")
        print("  2. You created a .env file")
        print("  3. The values in .env match PostgreSQL")
        print("Error detail:", e)