# app/auth_wrapper.py
# Wraps the real database functions so the frontend gets exactly the same names
# and return types it expects.

from app.db import run_query, run_command
import bcrypt

# ---------- password helpers ----------
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

# ---------- frontend functions ----------
def authenticate(username, password):
    """Returns {'user_id': int, 'role': str} or None"""
    rows = run_query(
        "SELECT user_id, password_hash, role, status FROM app_user WHERE username = %s",
        (username,)
    )
    if rows:
        user = rows[0]
        if user["status"] == "active" and verify_password(password, user["password_hash"]):
            return {"user_id": user["user_id"], "role": user["role"]}
    return None

def get_all_users():
    """Returns list of dicts with keys: user_id, username, role, is_active"""
    rows = run_query("SELECT user_id, username, role, status FROM app_user")
    return [
        {"user_id": r["user_id"], "username": r["username"],
         "role": r["role"], "is_active": r["status"] == "active"}
        for r in rows
    ]

def create_user(username, password, role, is_active=True):
    """Creates a new user in app_user."""
    if role not in ("Administrator", "Lecturer", "Student"):
        raise ValueError("Invalid role")
    hashed = hash_password(password)
    status = "active" if is_active else "inactive"
    run_command(
        "INSERT INTO app_user (username, password_hash, role, status) VALUES (%s, %s, %s, %s)",
        (username, hashed, role, status)
    )
    return True

def deactivate_user(user_id):
    run_command("UPDATE app_user SET status = 'inactive' WHERE user_id = %s", (user_id,))
    return True

def delete_user(user_id):
    run_command("DELETE FROM app_user WHERE user_id = %s", (user_id,))
    return True

def get_lecturer_id_from_user_id(user_id):
    """Maps user_id -> lecturer_id using the lecturer table."""
    rows = run_query("SELECT lecturer_id FROM lecturer WHERE user_id = %s", (user_id,))
    if rows:
        return rows[0]["lecturer_id"]
    return None