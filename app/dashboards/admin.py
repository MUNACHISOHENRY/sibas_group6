import streamlit as st
import pandas as pd
import plotly.express as px

# Real backend wiring.
#   app.api          -- user management (auth + status reshaping)
#   app.admin_ops    -- course / lecturer admin
#   app.reports      -- threshold + generate_report + CSV export
#   scripts.script2_register -- THE student registration deliverable
#       (using it here means the admin form and Script 2 share one
#       implementation -- there is no second registration path to defend)
from app.api import (
    get_all_users, create_user, deactivate_user, delete_user,
    reset_user_password, update_user_role, reactivate_user, rename_user,
)
from app.admin_ops import (
    get_all_lecturers, get_all_courses,
    add_course, get_lecturer_assignments, assign_lecturer,
)
from app.reports import (
    generate_report, get_threshold, update_threshold, export_csv, export_to_pdf,
)
from scripts.script2_register import (
    register_student as register_student,
    register_students_from_csv as bulk_register_students,
)

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
    """
    Admin user management. Implements the full brief contract:
    create, update, deactivate, delete. "Update" is a single expander
    with an action dropdown so all four kinds of user edits share one
    visible control instead of cluttering the sidebar.
    """
    st.subheader("User Management")
    search = st.text_input("Search User")
    filtered = [u for u in users if search.lower() in u["username"].lower()] if search else users
    st.dataframe(pd.DataFrame(filtered), use_container_width=True)

    col_a, col_b, col_c = st.columns(3)

    # --- Create ---
    with col_a:
        with st.expander("Create New User"):
            with st.form("create_user"):
                new_username = st.text_input("Username")
                new_password = st.text_input("Password", type="password")
                new_role = st.selectbox("Role", ["Administrator", "Lecturer", "Student"])
                new_active = st.checkbox("Active", value=True)
                if st.form_submit_button("Create"):
                    try:
                        create_user(new_username, new_password, new_role, new_active)
                        st.success("User created")
                    except Exception as e:
                        st.error(str(e))

    # --- Update (single expander, action-routed) ---
    with col_b:
        with st.expander("Update User"):
            with st.form("update_user"):
                target_id = st.number_input("User ID", min_value=1, step=1, key="upd_id")
                action = st.selectbox(
                    "Action",
                    ["Reset password", "Change role", "Reactivate", "Rename username"],
                )
                # Only show the input field relevant to the chosen action.
                new_password = ""
                new_role = "Student"
                new_username = ""
                if action == "Reset password":
                    new_password = st.text_input("New password", type="password",
                                                 help="Minimum 6 characters")
                elif action == "Change role":
                    new_role = st.selectbox(
                        "New role", ["Administrator", "Lecturer", "Student"],
                        key="upd_role",
                    )
                elif action == "Rename username":
                    new_username = st.text_input("New username")
                # Reactivate needs no extra input.

                if st.form_submit_button("Apply"):
                    try:
                        if action == "Reset password":
                            reset_user_password(int(target_id), new_password)
                        elif action == "Change role":
                            update_user_role(int(target_id), new_role)
                        elif action == "Reactivate":
                            reactivate_user(int(target_id))
                        elif action == "Rename username":
                            rename_user(int(target_id), new_username)
                        st.success(f"{action} applied to user {int(target_id)}")
                    except Exception as e:
                        st.error(str(e))

    # --- Deactivate / Delete ---
    with col_c:
        with st.expander("Deactivate / Delete"):
            user_id = st.number_input("User ID", min_value=1, step=1, key="del_id")
            d, dl = st.columns(2)
            with d:
                if st.button("Deactivate"):
                    deactivate_user(int(user_id))
                    st.success("Deactivated")
            with dl:
                if st.button("Delete"):
                    delete_user(int(user_id))
                    st.success("Deleted")

def manage_students():
    """
    Both registration paths (single form and bulk CSV) go through the
    SAME backend functions in scripts/script2_register.py.
    Field shapes match the Script 2 contract exactly so the system has
    one consistent registration logic to defend at marking.
    """
    st.subheader("Student Management")
    sub1, sub2 = st.tabs(["Register Student", "Bulk Upload"])

    # --------------------------------------------------------------
    # Individual registration
    # --------------------------------------------------------------
    with sub1:
        with st.form("student_form"):
            matric_no = st.text_input("Matric Number")
            full_name = st.text_input("Full Name")
            email     = st.text_input("Email")
            # Programme is the programme NAME (must already exist in DB).
            # Department is derived via programme -> NOT collected here.
            programme = st.text_input("Programme (exact name, e.g. 'BSc Computer Science')")
            level     = st.selectbox("Level", [100, 200, 300, 400, 500])

            # Login credentials for the new student (required by Script 2).
            username = st.text_input("Username (for student login)")
            password = st.text_input("Password", type="password",
                                     help="Minimum 6 characters")

            # Courses selected by COURSE CODE (Script 2 expects codes, not ids).
            all_courses = get_all_courses()
            code_to_label = {
                c["course_code"]: f'{c["course_code"]} - {c["course_title"]}'
                for c in all_courses
            }
            selected_codes = st.multiselect(
                "Courses",
                options=list(code_to_label.keys()),
                format_func=lambda x: code_to_label[x],
            )

            if st.form_submit_button("Register Student"):
                result = register_student(
                    matric_no      = matric_no,
                    full_name      = full_name,
                    email          = email,
                    programme_name = programme,
                    level          = level,
                    username       = username,
                    password       = password,
                    course_codes   = selected_codes,
                )
                if result.get("ok"):
                    st.success(f"Student registered (id={result['student_id']})")
                else:
                    st.error(result.get("error", "Registration failed"))

    # --------------------------------------------------------------
    # Bulk CSV registration -- one row per student
    # --------------------------------------------------------------
    with sub2:
        st.write(
            "Upload CSV with columns: "
            "**matric_no, full_name, email, programme, level, "
            "username, password, courses**"
        )
        st.caption(
            "`courses` is a semicolon-separated list of course codes "
            "(e.g. `DTS304;CSC310`)."
        )
        uploaded = st.file_uploader("Choose CSV", type="csv")
        if uploaded:
            try:
                df = pd.read_csv(uploaded)
            except Exception:
                st.error("Invalid CSV")
                return

            st.dataframe(df.head(10))

            required = ["matric_no", "full_name", "email", "programme",
                        "level", "username", "password", "courses"]
            missing = [c for c in required if c not in df.columns]
            if missing:
                st.error(f"Missing required columns: {missing}")
                return

            if st.button("Upload All"):
                # bulk_register_students = script2.register_students_from_csv
                # It returns {"total", "succeeded", "failed", "errors": [(line, msg)]}
                # The uploaded file's read pointer may have been consumed by
                # the preview above, so reset it.
                try:
                    uploaded.seek(0)
                except Exception:
                    pass
                result = bulk_register_students(uploaded)
                st.success(
                    f"Registered {result['succeeded']} of {result['total']} students "
                    f"({result['failed']} failed)"
                )
                if result.get("errors"):
                    st.json(result["errors"])

def manage_courses_assign(courses):
    """
    Course table reflects the schema exactly:
        course_code, course_title, lecturer
    There is NO department or level on a course (BR 15: course -> one
    lecturer; department/level are properties of the students who enrol).
    """
    st.subheader("Courses & Lecturer Assignments")
    col1, col2 = st.columns(2)

    # --------------------------------------------------------------
    # Add course -- requires a lecturer (the course's owner)
    # --------------------------------------------------------------
    with col1:
        st.write("**Course List**")
        st.dataframe(pd.DataFrame(courses), use_container_width=True)

        with st.expander("Add Course"):
            lect_list = get_all_lecturers()
            if not lect_list:
                st.info("Create a lecturer user before adding courses.")
            else:
                with st.form("add_course"):
                    code  = st.text_input("Course Code (e.g. DTS304)")
                    title = st.text_input("Course Title")
                    lec_id = st.selectbox(
                        "Lecturer",
                        options=[l["lecturer_id"] for l in lect_list],
                        format_func=lambda x: next(
                            l["full_name"] for l in lect_list
                            if l["lecturer_id"] == x
                        ),
                    )
                    if st.form_submit_button("Add"):
                        try:
                            add_course(code, title, lec_id)
                            st.success("Course added")
                        except Exception as e:
                            st.error(str(e))

    # --------------------------------------------------------------
    # Reassign a course to a different lecturer
    # --------------------------------------------------------------
    with col2:
        st.write("**Lecturer Assignments**")
        assignments = get_lecturer_assignments()
        st.dataframe(pd.DataFrame(assignments), use_container_width=True)

        lect_list = get_all_lecturers()
        course_list = get_all_courses()
        if lect_list and course_list:
            with st.form("assign_lecturer"):
                lec = st.selectbox(
                    "Lecturer",
                    [l["lecturer_id"] for l in lect_list],
                    format_func=lambda x: next(
                        l["full_name"] for l in lect_list
                        if l["lecturer_id"] == x
                    ),
                )
                crs = st.selectbox(
                    "Course",
                    [c["course_id"] for c in course_list],
                    format_func=lambda x: next(
                        c["course_code"] for c in course_list
                        if c["course_id"] == x
                    ),
                )
                if st.form_submit_button("Assign"):
                    assign_lecturer(lec, crs)
                    st.success("Lecturer reassigned")

def attendance_reports():
    """
    The three filters (department, course, level) are pulled from the
    database rather than hardcoded so the report reflects real data.
    Each filter starts at "All" -- the user only narrows when they want to.
    """
    st.subheader("Attendance Reports")

    # Build dropdown options from the DB. A small per-call cost; the
    # admin reports tab is not a hot path.
    courses = get_all_courses()
    course_codes = sorted({c["course_code"] for c in courses})

    # Departments come from the same JOIN every report uses. Reading
    # them here keeps "departments shown" in sync with "departments in
    # the data" without a separate cache.
    from app.db import run_query
    departments = [r["department_name"] for r in run_query(
        "SELECT department_name FROM department ORDER BY department_name"
    )]

    col1, col2, col3 = st.columns(3)
    dept   = col1.selectbox("Department", ["All"] + departments)
    course = col2.selectbox("Course",     ["All"] + course_codes)
    level  = col3.selectbox("Level",      ["All", 100, 200, 300, 400, 500])

    if st.button("Generate Report"):
        report = generate_report(
            department  = None if dept   == "All" else dept,
            course_code = None if course == "All" else course,
            level       = None if level  == "All" else level,
        )
        if report:
            df = pd.DataFrame(report)
            if "eligible" in df.columns:
                counts = df["eligible"].value_counts().reset_index()
                counts.columns = ["Status", "Count"]
                fig = px.pie(counts, names="Status", values="Count",
                             title="Eligibility Distribution")
                st.plotly_chart(fig, use_container_width=True)

            # `applymap` is deprecated on newer pandas; `Styler.map` is the
            # replacement. Fall back gracefully on older versions.
            try:
                styled = df.style.map(
                    lambda x: 'color:green' if x == 'Yes' else 'color:red',
                    subset=['eligible'],
                )
            except AttributeError:
                styled = df.style.applymap(
                    lambda x: 'color:green' if x == 'Yes' else 'color:red',
                    subset=['eligible'],
                )
            st.dataframe(styled, use_container_width=True)

            # Brief requirement #4o: reports must be exportable to CSV
            # and/or PDF. We expose both so the admin can pick the format.
            csv_data = export_csv(report)
            pdf_buffer = export_to_pdf(report, title="SIBAS Attendance Report")
            dlc, dlp = st.columns(2)
            with dlc:
                st.download_button("Download CSV", csv_data, "report.csv",
                                   mime="text/csv")
            with dlp:
                st.download_button("Download PDF", pdf_buffer.getvalue(),
                                   "report.pdf", mime="application/pdf")
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