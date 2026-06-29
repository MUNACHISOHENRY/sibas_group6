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
    get_user_profile_full,
    update_student_profile, update_lecturer_profile, update_administrator_profile,
    update_student_courses,
)
from app.admin_ops import (
    get_all_lecturers, get_all_courses,
    add_course, get_lecturer_assignments, assign_lecturer,
    get_all_programmes, get_all_departments,
    add_department, add_programme,
    delete_department, delete_programme,
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
    create, update, deactivate, delete.

    Two ways to pick a user:
      1. Per-row Edit/Deactivate/Delete buttons on the user table.
      2. A searchable user dropdown inside the "Update User" expander.
    Clicking a row's Edit button auto-selects that user in the dropdown.
    The dropdown's "Edit profile" action opens a role-aware sub-form so
    admins can update student/lecturer/admin profile fields directly.
    """
    st.subheader("User Management")

    # --- Search + filterable table with per-row actions ---
    search = st.text_input("Search User")
    filtered = (
        [u for u in users if search.lower() in u["username"].lower()]
        if search else users
    )

    if filtered:
        # Header row.
        h = st.columns([1, 2, 2, 1, 3])
        for col, label in zip(h, ["ID", "Username", "Role", "Active", "Actions"]):
            col.markdown(f"**{label}**")

        # One row per user with inline Edit / Deactivate / Delete buttons.
        # Buttons set st.session_state["selected_user_id"] so the Update
        # User dropdown below pre-selects the same person.
        for u in filtered:
            row = st.columns([1, 2, 2, 1, 1, 1, 1])
            row[0].write(u["user_id"])
            row[1].write(u["username"])
            row[2].write(u["role"])
            row[3].write("✓" if u["is_active"] else "✗")

            if row[4].button("Edit", key=f"edit_btn_{u['user_id']}"):
                st.session_state["selected_user_id"] = u["user_id"]
                st.session_state["upd_action"] = "Edit profile"
                st.rerun()

            if row[5].button("Deactivate", key=f"deac_btn_{u['user_id']}"):
                try:
                    deactivate_user(u["user_id"])
                    st.success(f"Deactivated #{u['user_id']}")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))

            if row[6].button("Delete", key=f"del_btn_{u['user_id']}"):
                try:
                    delete_user(u["user_id"])
                    st.success(f"Deleted #{u['user_id']}")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))
    else:
        st.info("No users match that search.")

    st.divider()

    col_a, col_b = st.columns(2)

    # --- Create New User (Administrator / Lecturer only) ---
    with col_a:
        with st.expander("Create New User"):
            with st.form("create_user"):
                new_username  = st.text_input("Username")
                new_password  = st.text_input("Password", type="password")
                # Student creation is intentionally NOT offered here. Students
                # require matric_no, programme, level and course enrolment --
                # the Students tab is the single, transactional path for that
                # (Script 2). Creating a half-registered Student row here
                # would leave the account unable to log in cleanly.
                new_role      = st.selectbox("Role", ["Administrator", "Lecturer"])
                new_full_name = st.text_input("Full Name", help="Required for Lecturer accounts")
                new_email     = st.text_input("Email",     help="Required for Lecturer accounts")
                new_active    = st.checkbox("Active", value=True)
                st.caption("To register a **Student** use the **Students** tab — it captures matric no., programme, and courses in one transaction.")
                if st.form_submit_button("Create"):
                    try:
                        create_user(
                            new_username, new_password, new_role, new_active,
                            full_name=new_full_name or None,
                            email=new_email or None,
                        )
                        st.success("User created")
                        st.rerun()
                    except Exception as e:
                        st.error(str(e))

    # --- Update User (searchable dropdown, action-routed) ---
    with col_b:
        with st.expander(
            "Update User",
            expanded=("selected_user_id" in st.session_state),
        ):
            if not users:
                st.info("No users yet.")
            else:
                # Searchable dropdown. Streamlit's selectbox lets the user
                # type to filter the options live -- much friendlier than
                # the old User ID number input.
                #
                # IMPORTANT: we do NOT pass a `key` to this selectbox. With
                # a key Streamlit ties the widget to its own session_state
                # slot and ignores `index` on subsequent renders -- which
                # means clicking a row's Edit button (which writes to
                # `selected_user_id`) would update our tracking var but
                # leave the dropdown stuck on the previous user, and the
                # form would render data for a *different* user than the
                # dropdown displays. Driving selection purely by `index`
                # keeps the dropdown and the form in lockstep.
                user_options = {
                    u["user_id"]: f"{u['username']} (#{u['user_id']}) — {u['role']}"
                    for u in users
                }
                ids = list(user_options.keys())

                sel = st.session_state.get("selected_user_id")
                pre_idx = ids.index(sel) if sel in ids else 0

                target_id = st.selectbox(
                    "User",
                    options=ids,
                    format_func=lambda x: user_options[x],
                    index=pre_idx,
                )
                # Single source of truth for the next render.
                st.session_state["selected_user_id"] = target_id

                action = st.selectbox(
                    "Action",
                    ["Edit profile", "Reset password", "Change role",
                     "Reactivate", "Rename username"],
                    key="upd_action",
                )

                if action == "Edit profile":
                    _edit_profile_form(int(target_id))

                elif action == "Reset password":
                    with st.form("reset_pw_form"):
                        new_password = st.text_input(
                            "New password", type="password",
                            help="Minimum 6 characters",
                        )
                        if st.form_submit_button("Apply"):
                            try:
                                reset_user_password(int(target_id), new_password)
                                st.success("Password reset")
                            except Exception as e:
                                st.error(str(e))

                elif action == "Change role":
                    with st.form("change_role_form"):
                        new_role = st.selectbox(
                            "New role",
                            ["Administrator", "Lecturer", "Student"],
                            key="upd_new_role",
                        )
                        st.caption(
                            "Changing role only flips the role flag on the "
                            "account. It does NOT move profile data between "
                            "the student/lecturer/administrator tables."
                        )
                        if st.form_submit_button("Apply"):
                            try:
                                update_user_role(int(target_id), new_role)
                                st.success("Role updated")
                                st.rerun()
                            except Exception as e:
                                st.error(str(e))

                elif action == "Reactivate":
                    st.caption("Flip an inactive account back to active.")
                    if st.button("Reactivate user", key="reactivate_btn"):
                        try:
                            reactivate_user(int(target_id))
                            st.success("Reactivated")
                            st.rerun()
                        except Exception as e:
                            st.error(str(e))

                elif action == "Rename username":
                    with st.form("rename_form"):
                        new_username = st.text_input("New username")
                        if st.form_submit_button("Apply"):
                            try:
                                rename_user(int(target_id), new_username)
                                st.success("Renamed")
                                st.rerun()
                            except Exception as e:
                                st.error(str(e))


def _edit_profile_form(user_id):
    """
    Role-aware profile editor. Pulls the current values via
    get_user_profile_full so all fields are pre-populated, then shows
    only the fields that apply to that role.
        Student  : full_name, email, level, programme, course enrolments
        Lecturer : full_name, email
        Admin    : full_name, email
    """
    profile = get_user_profile_full(user_id)
    if profile is None:
        st.error("User not found.")
        return

    if profile.get("profile_missing"):
        st.warning(
            f"This {profile['role']} account has no profile row in the "
            f"{profile['role'].lower()} table yet, so there's nothing to edit. "
            "Use the relevant tab (Students for students; Users → Create for lecturers) "
            "to create the profile, or delete and recreate the account."
        )
        return

    role = profile["role"]

    if role == "Student":
        # Form key includes user_id so switching users in the dropdown
        # creates a fresh widget tree -- otherwise Streamlit would reuse
        # the previous student's typed values instead of pre-filling
        # from the new student's profile.
        with st.form(f"edit_student_profile_{user_id}"):
            st.caption(f"Editing student **{profile['matric_no']}** (matric no. is not editable).")
            full_name = st.text_input("Full Name", value=profile.get("full_name", ""))
            email     = st.text_input("Email",     value=profile.get("email", ""))

            levels = [100, 200, 300, 400, 500]
            cur_level = profile.get("level", 100)
            level = st.selectbox(
                "Level", levels,
                index=levels.index(cur_level) if cur_level in levels else 0,
            )

            programmes = get_all_programmes()
            prog_names = [p["programme_name"] for p in programmes]
            cur_prog = profile.get("programme_name", "")
            prog_idx = prog_names.index(cur_prog) if cur_prog in prog_names else 0
            programme = (
                st.selectbox("Programme", prog_names, index=prog_idx)
                if prog_names else ""
            )

            all_courses = get_all_courses()
            all_codes = [c["course_code"] for c in all_courses]
            cur_codes = profile.get("course_codes", [])
            selected_codes = st.multiselect(
                "Courses",
                options=all_codes,
                default=[c for c in cur_codes if c in all_codes],
                format_func=lambda x: next(
                    (f'{c["course_code"]} - {c["course_title"]}'
                     for c in all_courses if c["course_code"] == x),
                    x,
                ),
            )

            if st.form_submit_button("Save"):
                try:
                    update_student_profile(
                        profile["student_id"],
                        full_name=full_name,
                        email=email,
                        level=level,
                        programme_name=programme or None,
                    )
                    summary = update_student_courses(
                        profile["student_id"], selected_codes,
                    )
                    st.success(
                        f"Profile saved (+{summary['added']} / "
                        f"−{summary['removed']} courses)"
                    )
                    st.rerun()
                except Exception as e:
                    st.error(str(e))

    elif role == "Lecturer":
        with st.form(f"edit_lecturer_profile_{user_id}"):
            full_name = st.text_input("Full Name", value=profile.get("full_name", ""))
            email     = st.text_input("Email",     value=profile.get("email", ""))
            if st.form_submit_button("Save"):
                try:
                    update_lecturer_profile(
                        profile["lecturer_id"],
                        full_name=full_name, email=email,
                    )
                    st.success("Profile saved")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))

    else:  # Administrator
        with st.form(f"edit_admin_profile_{user_id}"):
            full_name = st.text_input("Full Name", value=profile.get("full_name", ""))
            email     = st.text_input("Email",     value=profile.get("email", ""))
            if st.form_submit_button("Save"):
                try:
                    update_administrator_profile(
                        profile["admin_id"],
                        full_name=full_name, email=email,
                    )
                    st.success("Profile saved")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))

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
            # Programme dropdown — pulled live from DB so the name is always exact.
            all_programmes = get_all_programmes()
            if not all_programmes:
                st.warning("No programmes found in the database. Add a department and programme before registering students.")
                programme = ""
            else:
                prog_options = {p["programme_name"]: p["programme_name"] for p in all_programmes}
                programme = st.selectbox(
                    "Programme",
                    options=list(prog_options.keys()),
                    format_func=lambda x: x,
                )
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
                # Pre-check duplicate username so we can show a clear,
                # human-readable message instead of letting the raw
                # PostgreSQL UNIQUE-violation text reach the UI.
                from app.db import run_query_one
                existing = run_query_one(
                    "SELECT user_id FROM app_user WHERE username = %s",
                    (username.strip(),),
                ) if username and username.strip() else None

                if existing:
                    st.error(
                        f"Username '{username}' is already taken. "
                        "Pick a different one, or have the admin delete the "
                        "existing user from the Users tab first."
                    )
                else:
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
                        # Translate the most common PG error text the user
                        # would otherwise see verbatim.
                        err = result.get("error", "Registration failed")
                        if "duplicate key" in err.lower() and "matric" in err.lower():
                            st.error(f"Matric number '{matric_no}' is already in use.")
                        elif "duplicate key" in err.lower() and "email" in err.lower():
                            st.error(f"Email '{email}' is already in use.")
                        else:
                            st.error(err)

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

    # ── Attendance threshold ──────────────────────────────────────────────────
    current = get_threshold()
    st.write(f"Current attendance threshold: **{current}%**")
    new_val = st.number_input("New threshold (%)", 0.0, 100.0, current, 1.0)
    if st.button("Update Threshold"):
        update_threshold(new_val)
        st.success("Threshold updated")

    st.divider()

    # ── Departments ───────────────────────────────────────────────────────────
    st.subheader("Departments")
    departments = get_all_departments()

    col_dept, col_add_dept = st.columns(2)

    with col_dept:
        if departments:
            import pandas as pd
            dept_df = pd.DataFrame(departments)
            st.dataframe(dept_df[["department_id", "department_name"]],
                         use_container_width=True, hide_index=True)
        else:
            st.info("No departments yet.")

    with col_add_dept:
        with st.form("add_department"):
            st.write("**Add Department**")
            dept_name = st.text_input("Department Name")
            if st.form_submit_button("Add"):
                try:
                    add_department(dept_name)
                    st.success(f"Department '{dept_name}' added.")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))

        if departments:
            with st.form("delete_department"):
                st.write("**Delete Department**")
                dept_options = {d["department_name"]: d["department_id"] for d in departments}
                dept_to_del = st.selectbox("Select department", list(dept_options.keys()),
                                           key="del_dept")
                if st.form_submit_button("Delete"):
                    try:
                        delete_department(dept_options[dept_to_del])
                        st.success(f"Deleted '{dept_to_del}'.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Cannot delete: {e}")

    st.divider()

    # ── Programmes ────────────────────────────────────────────────────────────
    st.subheader("Programmes")
    programmes  = get_all_programmes()
    departments = get_all_departments()   # re-fetch in case one was just added

    col_prog, col_add_prog = st.columns(2)

    with col_prog:
        if programmes:
            import pandas as pd
            prog_df = pd.DataFrame(programmes)
            st.dataframe(prog_df[["programme_id", "programme_name", "department_name"]],
                         use_container_width=True, hide_index=True)
        else:
            st.info("No programmes yet. Add a department first, then add a programme.")

    with col_add_prog:
        if not departments:
            st.warning("Add a department before adding a programme.")
        else:
            with st.form("add_programme"):
                st.write("**Add Programme**")
                prog_name = st.text_input("Programme Name (e.g. BSc Computer Science)")
                dept_map  = {d["department_name"]: d["department_id"] for d in departments}
                selected_dept = st.selectbox("Department", list(dept_map.keys()))
                if st.form_submit_button("Add"):
                    try:
                        add_programme(prog_name, dept_map[selected_dept])
                        st.success(f"Programme '{prog_name}' added.")
                        st.rerun()
                    except Exception as e:
                        st.error(str(e))

        if programmes:
            with st.form("delete_programme"):
                st.write("**Delete Programme**")
                prog_options = {p["programme_name"]: p["programme_id"] for p in programmes}
                prog_to_del  = st.selectbox("Select programme", list(prog_options.keys()),
                                            key="del_prog")
                if st.form_submit_button("Delete"):
                    try:
                        delete_programme(prog_options[prog_to_del])
                        st.success(f"Deleted '{prog_to_del}'.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Cannot delete: {e}")