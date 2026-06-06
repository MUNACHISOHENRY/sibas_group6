from app.auth import register_user, login_user

# 1. Test Registration
try:
    print("Testing user registration...")
    # Registering a test student
    register_user("test_student", "password123", "Student")
    print("Registration successful!")
except Exception as e:
    print(f"Registration failed: {e}")

# 2. Test Login
print("\nTesting login...")
user, message = login_user("test_student", "password123")
if user:
    print(f"Login successful! Role: {user['role']}")
else:
    print(f"Login failed: {message}")