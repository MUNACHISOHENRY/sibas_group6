import streamlit as st
import pandas as pd

# Real backend wiring.
#   app.api wraps the auth + attendance modules into the names the
#   dashboards already use (create_session, get_my_sessions, etc.).
#   app.reports provides the unified generate_report and CSV export.
from app.api import (
    get_lecturer_id_from_user_id,
    get_assigned_courses,
    create_session,
    get_my_sessions,
    upload_attendance,
    get_session_records,
    get_students_for_session,
    override_attendance,
)
from app.reports import generate_report, export_csv

def require_role(*roles):
    if "role" not in st.session_state or st.session_state.role not in roles:
        st.error("Access denied")
        st.stop()

def lecturer_dashboard():
    require_role("Lecturer")

    st.title("Lecturer Dashboard")

    # Defensive: a Lecturer-role account without a matching lecturer row
    # cannot create sessions or own courses. Surface a helpful message
    # instead of crashing on the next None dereference.
    lect_id = get_lecturer_id_from_user_id(st.session_state["user_id"])
    if lect_id is None:
        st.error(
            "Your account has no lecturer record. "
            "Ask an administrator to add you to the Lecturer table."
        )
        return

    tabs = st.tabs(["Create Session", "Upload Attendance", "Override", "Reports"])

    with tabs[0]:
        create_session_page(lect_id)
    with tabs[1]:
        upload_attendance_page(lect_id)
    with tabs[2]:
        override_page(lect_id)
    with tabs[3]:
        lecturer_reports(lect_id)

def create_session_page(lect_id):
    """
    Per BR-19/20 a session is one course on one date. We don't ask for
    start/end times because the schema doesn't store them -- collecting
    UI data that vanishes would be dishonest at marking.
    """
    courses = get_assigned_courses(lect_id)
    if courses:
        with st.form("session"):
            course = st.selectbox(
                "Course",
                courses,
                format_func=lambda x: f'{x["course_code"]} - {x["title"]}',
            )
            date = st.date_input("Date")

            if st.form_submit_button("Create Session"):
                create_session(lect_id, course["course_id"], date)
                st.success("Session created")

def upload_attendance_page(lect_id):
    sessions = get_my_sessions(lect_id)
    if sessions:
        sess = st.selectbox(
            "Session",
            sessions,
            format_func=lambda s:f'{s["course_code"]} {s["session_date"]}'
        )

        file = st.file_uploader("Attendance CSV", type="csv")

        if file and st.button("Upload Attendance"):
            try:
                df = pd.read_csv(file)
            except:
                st.error("Invalid CSV")
                return
            if list(df.columns) != ["matric_no", "status"]:
                st.error("CSV must have exactly two columns: matric_no, status")
            else:
                valid = {"Present", "Absent"}
                if not set(df["status"]).issubset(valid):
                    st.error("Invalid status values (only Present/Absent allowed)")
                else:
                    result = upload_attendance(sess["session_id"], file)
                    st.success(f'Uploaded {result["success"]} records')
                    if result.get("errors"):
                        st.json(result["errors"])

def override_page(lect_id):
    """
    The override page is the canonical write path for individual
    attendance changes. It UPSERTs: if a record exists for that
    (session, student) we update it; if not we create it. So the same
    form covers "fix a mistake" and "add a missing student".
    The same backend (mark_attendance) is what the CSV upload uses --
    one write path, one set of business rules to defend.
    """
    sessions = get_my_sessions(lect_id)
    if not sessions:
        st.info("Create a session first.")
        return

    sess = st.selectbox(
        "Select Session",
        sessions,
        key="override",
        format_func=lambda s: f'{s["course_code"]} {s["session_date"]}',
    )

    # Read-only view of what's already on record.
    records = get_session_records(sess["session_id"])
    if records:
        st.write("**Current records for this session:**")
        st.dataframe(
            pd.DataFrame(records)[["matric_no", "full_name", "status"]],
            use_container_width=True,
        )
    else:
        st.info("No records yet for this session.")

    # Upsert form: pick any enrolled student, set status, save.
    students = get_students_for_session(sess["session_id"])
    if not students:
        st.warning("No students enrolled in this course.")
        return

    with st.form("override_form"):
        stu_opts = {
            s["student_id"]: f'{s["matric_no"]} - {s["full_name"]}'
            for s in students
        }
        stu_id = st.selectbox(
            "Student",
            options=list(stu_opts.keys()),
            format_func=lambda x: stu_opts[x],
        )
        new_status = st.radio("Status", ["Present", "Absent"], horizontal=True)
        if st.form_submit_button("Save"):
            try:
                override_attendance(sess["session_id"], stu_id, new_status)
                st.success("Record saved")
            except Exception as e:
                st.error(str(e))


def lecturer_reports(lect_id):
    courses = get_assigned_courses(lect_id)
    if courses:
        course = st.selectbox(
            "Course",
            courses,
            key="rep_course",
            format_func=lambda x: f'{x["course_code"]} - {x["title"]}',
        )
        if st.button("Generate Report"):
            # We have the course_code from the dropdown; pass it as
            # course_code so generate_report doesn't try to cast it to int.
            report = generate_report(course_code=course["course_code"])
            if report:
                st.dataframe(pd.DataFrame(report), use_container_width=True)
                csv_data = export_csv(report)
                st.download_button("Download CSV", csv_data, "lecturer_report.csv")
            else:
                st.info("No report data")
