import streamlit as st

# Real backend wiring.
#   get_student_profile, get_student_attendance, get_threshold all live
#   in app/reports.py -- they share the same DB layer and threshold source
#   as every other report in the system.
from app.reports import (
    get_student_profile,
    get_student_attendance,
    get_threshold,
)

def require_role(*roles):
    if "role" not in st.session_state or st.session_state.role not in roles:
        st.error("Access denied")
        st.stop()

def student_dashboard():
    require_role("Student")

    # Defensive: a user with role=Student should always have a matching
    # student row (Script 2 inserts both together). But if an admin
    # created a Student account via the Users tab without registering
    # them, we want a helpful message instead of a crash.
    profile = get_student_profile(st.session_state["user_id"])
    if profile is None:
        st.error(
            "Your account has no student record yet. "
            "Ask an administrator to complete your registration."
        )
        return

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

        with st.container(border=True):
            st.subheader(course["course_code"])
            st.write(course["title"])

            # When the course has no sessions yet (e.g. start of term), the
            # attendance formula (present/total) is undefined. We do NOT
            # show a percentage or an eligibility badge -- showing "100%
            # Eligible" for a student who has literally never attended
            # would be misleading. We surface "No sessions held yet"
            # instead. This matches how the admin report shows N/A.
            if total == 0:
                a, b = st.columns(2)
                a.metric("Attendance", "—")
                b.metric("Sessions", "0/0")
                st.info("No sessions held yet")
            else:
                pct = (present / total) * 100
                eligible = pct >= threshold

                st.progress(pct / 100)
                a, b = st.columns(2)
                a.metric("Attendance", f"{pct:.1f}%")
                b.metric("Sessions", f"{present}/{total}")
                if eligible:
                    st.success("Eligible for Examination")
                else:
                    st.error("Attendance Below Threshold")