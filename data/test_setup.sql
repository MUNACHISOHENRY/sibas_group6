-- =============================================================================
-- test_setup.sql  --  Optional test data for SIBAS
-- =============================================================================
-- Run this AFTER script1_schema.sql to seed the minimum data needed to
-- test Script 2 (student registration). It is NOT a deliverable -- it just
-- creates one department, one programme, one lecturer, and one course so
-- that the sample_students.csv has things to reference.
--
-- HOW TO RUN:
--     psql -U postgres -d sibas -f data/test_setup.sql
--
-- WHAT IT CREATES:
--     Department :  Computer Science
--     Programme  :  BSc Computer Science  (under Computer Science)
--     Lecturer   :  Dr. Sample Lecturer
--                   login -> username: lecturer1   password: Lecturer123
--     Course     :  DTS304  --  Data Management I  (taught by Dr. Sample)
-- =============================================================================


-- 1. Department
INSERT INTO department (department_name)
VALUES ('Computer Science');

-- 2. Programme (links to the department above by NAME so order doesn't matter
--    if you re-run this script after edits)
INSERT INTO programme (programme_name, department_id)
VALUES (
    'BSc Computer Science',
    (SELECT department_id FROM department WHERE department_name = 'Computer Science')
);

-- 3. A lecturer needs a user account first. Create the login, then the lecturer row.
INSERT INTO app_user (username, password_hash, role, status)
VALUES (
    'lecturer1',
    '$2b$12$2O7FtYEPgEvhqqaimUyzeO3djh61bPUvX7i6mf1vGwpHyZuDjIifi',  -- 'Lecturer123'
    'Lecturer',
    'active'
);

INSERT INTO lecturer (full_name, email, user_id)
VALUES (
    'Dr. Sample Lecturer',
    'sample.lecturer@pau.edu.ng',
    (SELECT user_id FROM app_user WHERE username = 'lecturer1')
);

-- 4. A course taught by that lecturer.
INSERT INTO course (course_code, course_title, lecturer_id)
VALUES (
    'DTS304',
    'Data Management I',
    (SELECT lecturer_id FROM lecturer WHERE email = 'sample.lecturer@pau.edu.ng')
);

-- Optionally add a second course so we can test multi-course enrollment.
INSERT INTO course (course_code, course_title, lecturer_id)
VALUES (
    'CSC310',
    'Database Management Systems',
    (SELECT lecturer_id FROM lecturer WHERE email = 'sample.lecturer@pau.edu.ng')
);
