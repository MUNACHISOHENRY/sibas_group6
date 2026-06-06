import bcrypt
from app.db import execute_query

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(password.encode('utf-8'), hashed_password.encode('utf-8'))

def register_user(username, password, role):
    # Enforce constraints
    if role not in ['Administrator', 'Lecturer', 'Student']:
        raise ValueError("Invalid role.")
        
    hashed_pw = hash_password(password)
    query = "INSERT INTO USERS (username, password_hash, role, status) VALUES (%s, %s, %s, 'active')"
    execute_query(query, (username, hashed_pw, role))

def login_user(username, password):
    query = "SELECT password_hash, role, status FROM USERS WHERE username = %s"
    results = execute_query(query, (username,))
    
    if results:
        hashed_pw, role, status = results[0]
        if status == 'active' and verify_password(password, hashed_pw):
            return {"role": role}, "Login successful."
    return None, "Invalid credentials or account inactive."