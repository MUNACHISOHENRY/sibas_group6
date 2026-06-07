import streamlit as st
import pandas as pd
import plotly.express as px
from backend import *


def require_role(*roles):
    if "role" not in st.session_state or st.session_state.role not in roles:
        st.error("Access denied")
        st.stop()

def admin_dashboard():
    require_role("Administrator")

    st.title("Administrator Dashboard")

    # KPIs
    users = get_all_users()
    lecturers = get_all_lecturers()
    courses = get_all_courses()
    a,b,c = st.columns(3)
    a.metric("Users", len(users))
    b.metric("Lecturers", len(lecturers))
    c.metric("Courses", len(courses))

    # Tab navigation
    tabs = st.tabs(["Users", "Students", "Courses & Assign", "Reports", "Configuration"])

    with tabs[0]:
        manage_users(users)
    with tabs[1]:
        manage_students()
    with tabs[2]:
        manage_courses_assign(courses)
    with tabs[3]:
        attendance_reports()
    with tabs[4]:
        config_page()

def manage_users(users):
    st.subheader("User Management")
    search = st.text_input("Search User")
    filtered = [u for u in users if search.lower() in u["username"].lower()] if search else users
    st.dataframe(pd.DataFrame(filtered), use_container_width=True)

    col_a, col_b = st.columns(2)
    with col_a:
        with st.expander("Create New User"):
            with st.form("create_user"):
                new_username = st.text_input("Username")
                new_password = st.text_input("Password", type="password")
                new_role = st.selectbox("Role", ["Administrator", "Lecturer", "Student"])
                new_active = st.checkbox("Active", value=True)
                if st.form_submit_button("Create"):
                    create_user(new_username, new_password, new_role, new_active)
                    st.success("User created")
    with col_b:
        with st.expander("Deactivate / Delete"):
            user_id = st.number_input("User ID", min_value=1, step=1)
            d, dl = st.columns(2)
            with d:
                if st.button("Deactivate"):
                    deactivate_user(user_id)
                    st.success("Deactivated")
            with dl:
                if st.button("Delete"):
                    delete_user(user_id)
                    st.success("Deleted")

def manage_students():
    st.subheader("Student Management")
    sub1, sub2 = st.tabs(["Register Student", "Bulk Upload"])

    with sub1:
        with st.form("student_form"):
            matric = st.text_input("Matric Number")
            full_name = st.text_input("Full Name")
            email = st.text_input("Email")
            dept = st.text_input("Department")
            programme = st.text_input("Programme")
            level = st.selectbox("Level",["100","200","300","400","500"])

            all_courses = get_all_courses()
            opts = {c["course_id"]:f'{c["course_code"]} - {c["title"]}' for c in all_courses}
            selected = st.multiselect("Courses", options=list(opts.keys()), format_func=lambda x: opts[x])

            if st.form_submit_button("Register Student"):
                register_student(matric,full_name,email,dept,programme,level,selected)
                st.success("Student registered")

    with sub2:
        st.write("Upload CSV with columns: matric_number, full_name, email, department, programme, level")
        uploaded = st.file_uploader("Choose CSV", type="csv")
        if uploaded:
            try:
                df = pd.read_csv(uploaded)
            except:
                st.error("Invalid CSV")
                return
            st.dataframe(df.head(10))
            required = ["matric_number","full_name","email","department","programme","level"]
            if not all(col in df.columns for col in required):
                st.error("Missing required columns")
                return
            if st.button("Upload All"):
                result = bulk_register_students(uploaded)
                st.success(f"Registered {result['success']} students")
                if result.get("errors"):
                    st.json(result["errors"])

def manage_courses_assign(courses):
    st.subheader("Courses & Lecturer Assignments")
    col1, col2 = st.columns(2)
    with col1:
        st.write("**Course List**")
        st.dataframe(pd.DataFrame(courses), use_container_width=True)
        with st.expander("Add Course"):
            with st.form("add_course"):
                code = st.text_input("Course Code")
                title = st.text_input("Title")
                dept = st.text_input("Department")
                lvl = st.selectbox("Level", ["100","200","300","400","500"])
                if st.form_submit_button("Add"):
                    add_course(code, title, dept, lvl)
                    st.success("Course added")
    with col2:
        st.write("**Lecturer Assignments**")
        assignments = get_lecturer_assignments()
        st.dataframe(pd.DataFrame(assignments), use_container_width=True)
        with st.form("assign_lecturer"):
            lect_list = get_all_lecturers()
            course_list = get_all_courses()
            lec = st.selectbox("Lecturer", [l["lecturer_id"] for l in lect_list],
                               format_func=lambda x: next(l["full_name"] for l in lect_list if l["lecturer_id"]==x))
            crs = st.selectbox("Course", [c["course_id"] for c in course_list],
                               format_func=lambda x: next(c["course_code"] for c in course_list if c["course_id"]==x))
            if st.form_submit_button("Assign"):
                assign_lecturer(lec, crs)
                st.success("Lecturer assigned")

def attendance_reports():
    st.subheader("Attendance Reports")
    col1,col2,col3 = st.columns(3)
    dept = col1.selectbox("Department", ["All","Computer Science","Software Engineering"])
    course = col2.selectbox("Course", ["All","CSC101","CSC201","SE301"])
    level = col3.selectbox("Level", ["All","100","200","300","400"])

    if st.button("Generate Report"):
        report = generate_report(
            department=None if dept=="All" else dept,
            course_id=None if course=="All" else course,
            level=None if level=="All" else level
        )
        if report:
            df = pd.DataFrame(report)
            if "eligible" in df.columns:
                counts = df["eligible"].value_counts().reset_index()
                counts.columns = ["Status","Count"]
                fig = px.pie(counts, names="Status", values="Count", title="Eligibility Distribution")
                st.plotly_chart(fig, use_container_width=True)

            st.dataframe(df.style.applymap(lambda x: 'color:green' if x=='Yes' else 'color:red', subset=['eligible']), use_container_width=True)
            csv_data = export_csv(report)
            st.download_button("Download CSV", csv_data, "report.csv")
        else:
            st.info("No data found")

def config_page():
    st.subheader("Configuration")
    current = get_threshold()
    st.write(f"Current attendance threshold: **{current}%**")
    new_val = st.number_input("New threshold (%)", 0.0, 100.0, current, 1.0)
    if st.button("Update Threshold"):
        update_threshold(new_val)
        st.success("Threshold updated")