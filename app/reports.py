# app/reports.py

import pandas as pd
from io import BytesIO

from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet




def fetch_attendance_data(conn):
    """
    Fetch attendance data from PostgreSQL
    """
    query = """
    SELECT 
        s.matric_no,
        s.full_name,
        d.name AS department,
        c.course_code,
        COUNT(a.session_id) AS total_sessions,
        SUM(CASE WHEN a.status = 'Present' THEN 1 ELSE 0 END) AS sessions_present
    FROM attendance a
    JOIN students s ON s.id = a.student_id
    JOIN courses c ON c.id = a.course_id
    JOIN departments d ON d.id = s.department_id
    GROUP BY s.matric_no, s.full_name, d.name, c.course_code
    ORDER BY s.full_name;
    """
    return pd.read_sql(query, conn)


def calculate_attendance(df):
    """
    Compute attendance percentage
    """
    df["attendance_percent"] = (
        df["sessions_present"] / df["total_sessions"] * 100
    ).round(2)

    return df


def generate_student_report(df, matric_no):
    """
    Filter report for a single student
    """
    return df[df["matric_no"] == matric_no]


def generate_course_report(df, course_code):
    """
    Filter report for a specific course
    """
    return df[df["course_code"] == course_code]


def generate_department_report(df, department):
    """
    Filter report for a department
    """
    return df[df["department"] == department]


def export_to_csv(df):
    """
    Export report to CSV
    """
    return df.to_csv(index=False).encode("utf-8")



def add_eligibility_flag(df, threshold=80):
    """
    Add eligibility status based on attendance %
    """
    df["status"] = df["attendance_percent"].apply(
        lambda x: "Eligible" if x >= threshold else "Ineligible"
    )
    return df


def export_to_pdf(df, title="Attendance Report"):
    """
    Export report to PDF
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)

    elements = []
    styles = getSampleStyleSheet()

    elements.append(Paragraph(title, styles["Title"]))

    data = [df.columns.tolist()] + df.values.tolist()

    table = Table(data)

    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 1, colors.black),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
    ]))

    elements.append(table)

    doc.build(elements)
    buffer.seek(0)

    return buffer




def generate_full_report(conn):
    """
    Full report generation pipeline
    """
    df = fetch_attendance_data(conn)     
    df = calculate_attendance(df)        
    df = add_eligibility_flag(df)        

    return df
