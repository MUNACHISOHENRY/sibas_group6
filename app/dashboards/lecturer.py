import streamlit as st
import pandas as pd

# Dummy backend – replace with real imports later
from backend import *

def require_role(*roles):
    if "role" not in st.session_state or st.session_state.role not in roles:
        st.error("Access denied")
        st.stop()

def lecturer_dashboard():
    require_role("Lecturer")

    st.title("Lecturer Dashboard")

    lect_id = get_lecturer_id_from_user_id(st.session_state["user_id"])

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
    courses = get_assigned_courses(lect_id)
    if courses:
        with st.form("session"):
            course = st.selectbox(
                "Course",
                courses,
                format_func=lambda x:f'{x["course_code"]} - {x["title"]}'
            )
            date = st.date_input("Date")
            start = st.time_input("Start")
            end = st.time_input("End")

            if st.form_submit_button("Create Session"):
                create_session(lect_id,course["course_id"],date,start,end)
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
            if list(df.columns) != ["matric_number", "status"]:
                st.error("CSV must have exactly two columns: matric_number, status")
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
    sessions = get_my_sessions(lect_id)
    if sessions:
        sess = st.selectbox(
            "Select Session",
            sessions,
            key="override",
            format_func=lambda s:f'{s["course_code"]} {s["session_date"]}'
        )

        records = get_session_records(sess["session_id"])
        if records:
            df = pd.DataFrame(records)
            st.dataframe(df, use_container_width=True)
            rec_id = st.selectbox("Record ID", [r["record_id"] for r in records])
            new_status = st.radio("New Status", ["Present","Absent"])
            if st.button("Override"):
                override_attendance(rec_id, new_status)
                st.success("Record updated")
        else:
            st.info("No records for this session")

def lecturer_reports(lect_id):
    courses = get_assigned_courses(lect_id)
    if courses:
        course = st.selectbox(
            "Course",
            courses,
            key="rep_course",
            format_func=lambda x:f'{x["course_code"]} - {x["title"]}'
        )
        if st.button("Generate Report"):
            report = generate_report(course_id=course["course_code"])
            if report:
                st.dataframe(pd.DataFrame(report), use_container_width=True)
                csv_data = export_csv(report)
                st.download_button("Download CSV", csv_data, "lecturer_report.csv")
            else:
                st.info("No report data")