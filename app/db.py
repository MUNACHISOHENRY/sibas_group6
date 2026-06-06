import psycopg2
import os
from pathlib import Path
from dotenv import load_dotenv

# --- SETUP AND CONFIGURATION ---
# Points to the root directory (one level above 'app') to find the .env file
base_path = Path(__file__).resolve().parent.parent
env_path = base_path / '.env'

# Explicitly load the .env file
load_dotenv(dotenv_path=env_path)

def get_db_connection():
    """
    Creates a database connection using variables from the .env file.
    Returns the connection object or None if connection fails.
    """
    db_name = os.getenv("DB_NAME")
    db_user = os.getenv("DB_USER")
    db_pass = os.getenv("DB_PASS")
    db_host = os.getenv("DB_HOST", "localhost")
    db_port = os.getenv("DB_PORT", "5432")

    # Diagnostic check: ensure credentials are loaded
    if not all([db_name, db_user, db_pass]):
        print(f"CRITICAL ERROR: Missing DB credentials in .env file at {env_path}")
        print(f"Loaded: DB_NAME={db_name}, DB_USER={db_user}, DB_PASS={bool(db_pass)}")
        return None

    try:
        conn = psycopg2.connect(
            dbname=db_name,
            user=db_user,
            password=db_pass,
            host=db_host,
            port=db_port
        )
        return conn
    except Exception as e:
        print(f"Database connection error: {e}")
        return None

def execute_query(query, params=()):
    """
    Executes a SQL query safely and returns results if available.
    Use this for all SELECT, INSERT, UPDATE, and DELETE operations.
    """
    conn = get_db_connection()
    if conn is None:
        raise ConnectionError("Could not establish connection to the database.")
    
    result = None
    try:
        with conn.cursor() as cur:
            cur.execute(query, params)
            # Fetch results only if the query returns data (e.g., SELECT)
            if cur.description:
                result = cur.fetchall()
            conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Query Execution Error: {e}")
        raise e
    finally:
        conn.close()
    
    return result