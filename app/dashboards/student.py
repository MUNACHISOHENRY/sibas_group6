import streamlit as st

# Dummy backend – replace with real imports later
from backend import *

def require_role(*roles):
    if "role" not in st.session_state or st.session_state.role not in roles:
        st.error("Access denied")
        st.stop()

def student_dashboard():
    require_role("Student")

    profile = get_student_profile(st.session_state["user_id"])
    attendance = get_student_attendance(profile["student_id"])
    threshold = get_threshold()

    st.title("Student Portal")
    st.write(f"Welcome, **{profile['full_name']}**")

    c1,c2,c3 = st.columns(3)
    c1.metric("Matric", profile["matric_number"])
    c2.metric("Programme", profile["programme"])
    c3.metric("Threshold", f"{threshold}%")

    for course in attendance:
        total = course["total"]
        present = course["present"]
        pct = (present/total)*100 if total>0 else 100
        eligible = pct >= threshold

        with st.container(border=True):
            st.subheader(course["course_code"])
            st.write(course["title"])
            st.progress(pct/100)

            a,b = st.columns(2)
            a.metric("Attendance", f"{pct:.1f}%")
            b.metric("Sessions", f'{course["present"]}/{course["total"]}')

            if eligible:
                st.success("Eligible for Examination")
            else:
                st.error("Attendance Below Threshold")