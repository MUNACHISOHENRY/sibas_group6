# backend.py - Dummy backend that fulfills all SIBAS frontend requirements
# Replace this file with the PostgreSQL implementation using the same function names and returns.

import pandas as pd
import io

# ---------- Authentication ----------
def authenticate(username, password):
    test_users = {
        "admin":         {"user_id": 1, "role": "Administrator", "password": "admin123"},
        "lecturer1":     {"user_id": 2, "role": "Lecturer",      "password": "lect123"},
        "lecturer2":     {"user_id": 5, "role": "Lecturer",      "password": "lect123"},
        "student1":      {"user_id": 3, "role": "Student",       "password": "stud123"},
        "student2":      {"user_id": 4, "role": "Student",       "password": "stud123"},
    }
    user = test_users.get(username)
    if user and user["password"] == password:
        return {"user_id": user["user_id"], "role": user["role"]}
    return None

# ---------- User Management ----------
def get_all_users():
    return [
        {"user_id": 1, "username": "admin",     "role": "Administrator", "is_active": True},
        {"user_id": 2, "username": "lecturer1", "role": "Lecturer",      "is_active": True},
        {"user_id": 3, "username": "student1",  "role": "Student",       "is_active": True},
    ]

def create_user(username, password, role, is_active):
    # In real backend: hash password, insert into users table
    return True

def update_user(user_id, new_role=None, new_active=None, new_password=None):
    # Update role, active status, and/or password
    return True

def deactivate_user(user_id):
    return True

def delete_user(user_id):
    return True

# ---------- Student Management ----------
def register_student(matric, full_name, email, dept, programme, level, course_ids):
    # Create student record and enroll in chosen courses
    return True

def bulk_register_students(csv_file):
    df = pd.read_csv(csv_file)
    # In real backend: parse optional 'course_codes' column, register each student, enroll
    return {"success": len(df), "errors": []}

# ---------- Courses & Assignments ----------
def get_all_courses():
    return [
        {"course_id": 1, "course_code": "CSC101", "title": "Intro to Computer Science", "department": "Computer Science", "level": "100"},
        {"course_id": 2, "course_code": "CSC201", "title": "Data Structures", "department": "Computer Science", "level": "200"},
        {"course_id": 3, "course_code": "SE301",  "title": "Software Engineering Principles", "department": "Software Engineering", "level": "300"},
    ]

def add_course(course_code, title, department, level):
    return True

def get_all_lecturers():
    return [
        {"lecturer_id": 1, "full_name": "Dr. Adebayo", "staff_id": "L001"},
        {"lecturer_id": 2, "full_name": "Prof. Obi",    "staff_id": "L002"},
    ]

def get_lecturer_assignments():
    return [
        {"assignment_id": 1, "lecturer_name": "Dr. Adebayo", "course_code": "CSC101"},
        {"assignment_id": 2, "lecturer_name": "Prof. Obi",    "course_code": "CSC201"},
    ]

def assign_lecturer(lecturer_id, course_id):
    return True

# ---------- Lecturer Helpers ----------
def get_lecturer_id_from_user_id(user_id):
    # Real backend: SELECT lecturer_id FROM lecturers WHERE user_id = %s
    mapping = {2: 1, 5: 2}   # user_id -> lecturer_id for dummy
    return mapping.get(user_id)

def get_assigned_courses(lecturer_id):
    if lecturer_id == 1:
        return [{"course_id": 1, "course_code": "CSC101", "title": "Intro to CS"}]
    elif lecturer_id == 2:
        return [{"course_id": 2, "course_code": "CSC201", "title": "Data Structures"}]
    return []

# ---------- Attendance Sessions ----------
def create_session(lecturer_id, course_id, session_date, start_time, end_time):
    return 1   # new session_id

def get_my_sessions(lecturer_id):
    if lecturer_id == 1:
        return [
            {"session_id": 1, "course_code": "CSC101", "session_date": "2026-05-20", "start_time": "09:00", "end_time": "11:00"},
            {"session_id": 2, "course_code": "CSC101", "session_date": "2026-05-21", "start_time": "09:00", "end_time": "11:00"},
        ]
    return []

def upload_attendance(session_id, csv_file):
    df = pd.read_csv(csv_file)
    return {"success": len(df), "errors": []}

def get_session_records(session_id):
    return [
        {"record_id": 1, "matric_number": "PAU/2023/001", "full_name": "John Doe",  "status": "Present", "is_override": False},
        {"record_id": 2, "matric_number": "PAU/2023/002", "full_name": "Jane Smith","status": "Absent",  "is_override": False},
    ]

def override_attendance(record_id, new_status):
    return True

# ---------- Student Functions ----------
def get_student_profile(user_id):
    return {
        "student_id": 1,
        "full_name": "John Doe",
        "matric_number": "PAU/2023/001",
        "department": "Computer Science",
        "programme": "BSc CS",
        "level": "200"
    }

def get_student_attendance(student_id):
    return [
        {"course_code": "CSC101", "title": "Introduction to Computer Science", "present": 10, "total": 12},
        {"course_code": "CSC201", "title": "Data Structures",             "present": 8,  "total": 10},
    ]

# ---------- Reports ----------
def generate_report(department=None, course_id=None, level=None):
    return [
        {"student_name": "John Doe",   "matric": "PAU/2023/001", "course": "CSC101", "attendance": 83.3, "eligible": "Yes"},
        {"student_name": "Jane Smith", "matric": "PAU/2023/002", "course": "CSC101", "attendance": 75.0, "eligible": "No"},
        {"student_name": "John Doe",   "matric": "PAU/2023/001", "course": "CSC201", "attendance": 80.0, "eligible": "Yes"},
    ]

def get_threshold():
    return 80.0

def update_threshold(new_value):
    return True

# ---------- Export Helpers ----------
def export_csv(report_data):
    df = pd.DataFrame(report_data)
    output = io.BytesIO()
    df.to_csv(output, index=False)
    output.seek(0)
    return output

def export_pdf(report_data):
    # For real PDF: use fpdf or reportlab. Returns bytes.
    return export_csv(report_data)   # placeholder