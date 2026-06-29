"""
app/admin_ops.py  --  Administrator-only operations on courses and lecturers.

The admin dashboard's "Courses & Assign" tab is the only place that uses
these functions. They were grouped into their own module (rather than added
to api.py) because they cover a different surface area: course creation
and lecturer assignment, not authentication or attendance.

All DB access goes through app/db.py with parameterised queries.

Functions:
    get_all_lecturers()        -> list of {lecturer_id, full_name, email}
    get_all_courses()          -> list of {course_id, course_code, course_title,
                                            title, lecturer_id, lecturer_name}
    add_course(code, title, lecturer_id)
    get_lecturer_assignments() -> list of {lecturer_name, course_code, course_title}
    assign_lecturer(lecturer_id, course_id)
"""

from app.db import run_query, run_command


def get_all_programmes() -> list:
    """
    Every programme in the system, joined with its department name.
    Used to populate the programme dropdown when registering a student.
    """
    return run_query(
        """
        SELECT
            p.programme_id,
            p.programme_name,
            d.department_name
        FROM   programme p
        JOIN   department d ON d.department_id = p.department_id
        ORDER  BY p.programme_name
        """
    )


def get_all_departments() -> list:
    """All departments, ordered by name."""
    return run_query(
        "SELECT department_id, department_name FROM department ORDER BY department_name"
    )


def add_department(name: str):
    if not name or not name.strip():
        raise ValueError("Department name is required.")
    run_command(
        "INSERT INTO department (department_name) VALUES (%s)",
        (name.strip(),),
    )
    return True


def add_programme(programme_name: str, department_id: int):
    if not programme_name or not programme_name.strip():
        raise ValueError("Programme name is required.")
    if department_id is None:
        raise ValueError("Department is required.")
    run_command(
        "INSERT INTO programme (programme_name, department_id) VALUES (%s, %s)",
        (programme_name.strip(), int(department_id)),
    )
    return True


def delete_department(department_id: int):
    """
    Deletes a department. Will fail (FK RESTRICT) if any programme still
    references it -- the caller should catch and surface that error.
    """
    run_command(
        "DELETE FROM department WHERE department_id = %s",
        (int(department_id),),
    )
    return True


def delete_programme(programme_id: int):
    """
    Deletes a programme. Will fail (FK RESTRICT) if any student is
    enrolled in it.
    """
    run_command(
        "DELETE FROM programme WHERE programme_id = %s",
        (int(programme_id),),
    )
    return True


def get_all_lecturers() -> list:
    """
    Every lecturer with login + profile info.

    Useful for: the Add Course form (we need a dropdown to pick the lecturer
    who will own the course) and the Assign Lecturer form (we need to pick
    a lecturer to reassign an existing course to).
    """
    return run_query(
        """
        SELECT
            l.lecturer_id,
            l.full_name,
            l.email,
            l.user_id
        FROM   lecturer l
        ORDER  BY l.full_name
        """
    )


def get_all_courses() -> list:
    """
    Every course in the system, joined with its owning lecturer.

    The dashboard sometimes reads c["title"], sometimes c["course_title"];
    we expose both so the UI doesn't have to be touched again.
    """
    rows = run_query(
        """
        SELECT
            c.course_id,
            c.course_code,
            c.course_title,
            c.lecturer_id,
            l.full_name AS lecturer_name
        FROM   course c
        JOIN   lecturer l ON l.lecturer_id = c.lecturer_id
        ORDER  BY c.course_code
        """
    )
    for r in rows:
        r["title"] = r["course_title"]
    return rows


def add_course(course_code: str, course_title: str, lecturer_id: int):
    """
    Add a course.

    Business rule 15: a course belongs to exactly one lecturer, picked here.
    The course table has no department or level columns -- our 3NF schema
    reaches those facts through the students who enrol in the course.
    """
    if not course_code or not course_code.strip():
        raise ValueError("course_code is required")
    if not course_title or not course_title.strip():
        raise ValueError("course_title is required")
    if lecturer_id is None:
        raise ValueError("lecturer_id is required")

    run_command(
        """
        INSERT INTO course (course_code, course_title, lecturer_id)
        VALUES (%s, %s, %s)
        """,
        (course_code.strip(), course_title.strip(), int(lecturer_id)),
    )
    return True


def get_lecturer_assignments() -> list:
    """
    A flat read of every (lecturer, course) pairing -- one row per course.

    A course can only have one lecturer (BR 15) so this is essentially
    "courses joined to their owner". Sorted by lecturer so the dashboard
    can show them grouped naturally.
    """
    return run_query(
        """
        SELECT
            l.lecturer_id,
            l.full_name   AS lecturer_name,
            c.course_id,
            c.course_code,
            c.course_title
        FROM   lecturer l
        LEFT JOIN course c ON c.lecturer_id = l.lecturer_id
        ORDER  BY l.full_name, c.course_code
        """
    )


def assign_lecturer(lecturer_id: int, course_id: int):
    """
    Reassign an existing course to a different lecturer.

    Note: this UPDATES the course's lecturer_id; it does not create a new
    row. There is no separate lecturer_course junction table -- the
    relationship is stored directly on the course row.
    """
    run_command(
        "UPDATE course SET lecturer_id = %s WHERE course_id = %s",
        (int(lecturer_id), int(course_id)),
    )
    return True
