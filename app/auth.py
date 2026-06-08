import bcrypt
from app.db import run_query_one, run_command


def hash_password(password: str) -> str:
    return bcrypt.hashpw(
        password.encode("utf-8"),
        bcrypt.gensalt()
    ).decode("utf-8")


def verify_password(password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(
        password.encode("utf-8"),
        hashed_password.encode("utf-8")
    )


def register_user(username, password, role):
    """
    Creates a new record in app_user.

    Schema roles:
        Administrator
        Lecturer
        Student
    """

    if role not in ["Administrator", "Lecturer", "Student"]:
        raise ValueError("Invalid role.")

    hashed_pw = hash_password(password)

    query = """
        INSERT INTO app_user
        (
            username,
            password_hash,
            role,
            status
        )
        VALUES
        (
            %s,
            %s,
            %s,
            'active'
        )
    """

    return run_command(
        query,
        (
            username,
            hashed_pw,
            role
        )
    )


def login_user(username, password):
    """
    Authenticate against app_user table.
    """

    query = """
        SELECT
            user_id,
            username,
            password_hash,
            role,
            status
        FROM app_user
        WHERE username = %s
    """

    user = run_query_one(query, (username,))

    if not user:
        return None, "Invalid credentials or account inactive."

    if user["status"] != "active":
        return None, "Invalid credentials or account inactive."

    if not verify_password(password, user["password_hash"]):
        return None, "Invalid credentials or account inactive."

    return {
        "user_id": user["user_id"],
        "username": user["username"],
        "role": user["role"]
    }, "Login successful."