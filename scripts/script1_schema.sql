-- =============================================================================
-- SCRIPT 1 :  SIBAS DATABASE SCHEMA
-- DTS304 Data Management I  --  2025/2026 Second Semester Project
-- Group 6  --  Pan-Atlantic University, School of Science and Technology
-- =============================================================================


-- ---------- 1. CREATE THE DATABASE -----------------------------------------
-- CREATE DATABASE can't run from inside the database it is creating, so this
-- block must be executed while connected to a different database (usually
-- the default 'postgres' database that ships with every install).

DROP DATABASE IF EXISTS sibas;
CREATE DATABASE sibas;

\connect sibas


-- ===========================================================================
-- 2. TABLES
-- Tables are created top-down: every referenced table exists before any
-- table that points to it.
-- ===========================================================================


-- ---------- DEPARTMENT -----------------------------------------------------
-- Academic departments (e.g. Computer Science, Mass Communication).
CREATE TABLE department (
    department_id   SERIAL       PRIMARY KEY,
    department_name VARCHAR(100) NOT NULL UNIQUE
);


-- ---------- PROGRAMME ------------------------------------------------------
-- A programme of study (e.g. BSc Computer Science) belongs to one department.
-- Business rule: one department -> many programmes.
CREATE TABLE programme (
    programme_id   SERIAL       PRIMARY KEY,
    programme_name VARCHAR(150) NOT NULL UNIQUE,
    department_id  INTEGER      NOT NULL,

    CONSTRAINT fk_programme_department
        FOREIGN KEY (department_id)
        REFERENCES department (department_id)
        ON DELETE RESTRICT
);


-- ---------- APP_USER -------------------------------------------------------
-- One row per person who can log in. Holds AUTHENTICATION data only.
-- (Personal details like full_name live in the role-specific tables.)
-- Named 'app_user' because 'user' is a reserved word in PostgreSQL.
CREATE TABLE app_user (
    user_id       SERIAL       PRIMARY KEY,
    username      VARCHAR(50)  NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,        -- bcrypt output (~60 chars)
    role          VARCHAR(20)  NOT NULL,
    status        VARCHAR(10)  NOT NULL DEFAULT 'active',
    created_at    TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- Business rule 3: role must be one of the three allowed values.
    CONSTRAINT chk_user_role
        CHECK (role IN ('Administrator', 'Lecturer', 'Student')),

    -- Business rule 4: status is either active or inactive.
    CONSTRAINT chk_user_status
        CHECK (status IN ('active', 'inactive'))
);


-- ---------- STUDENT --------------------------------------------------------
-- Note: NO department_id column. Department is derived through the programme
-- (STUDENT.programme_id -> PROGRAMME.department_id). Storing it again here
-- would be a transitive dependency and break 3NF.
CREATE TABLE student (
    student_id    SERIAL       PRIMARY KEY,
    matric_no     VARCHAR(20)  NOT NULL UNIQUE,
    full_name     VARCHAR(150) NOT NULL,
    email         VARCHAR(150) NOT NULL UNIQUE,
    programme_id  INTEGER      NOT NULL,
    user_id       INTEGER      NOT NULL UNIQUE,   -- one user -> one student
    level         INTEGER      NOT NULL,

    CONSTRAINT fk_student_programme
        FOREIGN KEY (programme_id)
        REFERENCES programme (programme_id)
        ON DELETE RESTRICT,

    CONSTRAINT fk_student_user
        FOREIGN KEY (user_id)
        REFERENCES app_user (user_id)
        ON DELETE CASCADE,

    -- Standard Nigerian undergraduate levels.
    CONSTRAINT chk_student_level
        CHECK (level IN (100, 200, 300, 400, 500))
);


-- ---------- LECTURER -------------------------------------------------------
CREATE TABLE lecturer (
    lecturer_id SERIAL       PRIMARY KEY,
    full_name   VARCHAR(150) NOT NULL,
    email       VARCHAR(150) NOT NULL UNIQUE,
    user_id     INTEGER      NOT NULL UNIQUE,

    CONSTRAINT fk_lecturer_user
        FOREIGN KEY (user_id)
        REFERENCES app_user (user_id)
        ON DELETE CASCADE
);


-- ---------- ADMINISTRATOR --------------------------------------------------
CREATE TABLE administrator (
    admin_id  SERIAL       PRIMARY KEY,
    full_name VARCHAR(150) NOT NULL,
    email     VARCHAR(150) NOT NULL UNIQUE,
    user_id   INTEGER      NOT NULL UNIQUE,

    CONSTRAINT fk_admin_user
        FOREIGN KEY (user_id)
        REFERENCES app_user (user_id)
        ON DELETE CASCADE
);


-- ---------- COURSE ---------------------------------------------------------
-- Business rule 15: a course is assigned to exactly one lecturer.
CREATE TABLE course (
    course_id    SERIAL       PRIMARY KEY,
    course_code  VARCHAR(20)  NOT NULL UNIQUE,    -- e.g. 'DTS304'
    course_title VARCHAR(150) NOT NULL,
    lecturer_id  INTEGER      NOT NULL,

    CONSTRAINT fk_course_lecturer
        FOREIGN KEY (lecturer_id)
        REFERENCES lecturer (lecturer_id)
        ON DELETE RESTRICT
);


-- ---------- STUDENT_COURSE (junction table) -------------------------------
-- Resolves the many-to-many relationship between students and courses
-- (business rules 11 and 12).
CREATE TABLE student_course (
    student_course_id SERIAL    PRIMARY KEY,
    student_id        INTEGER   NOT NULL,
    course_id         INTEGER   NOT NULL,
    registered_at     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_sc_student
        FOREIGN KEY (student_id)
        REFERENCES student (student_id)
        ON DELETE CASCADE,

    CONSTRAINT fk_sc_course
        FOREIGN KEY (course_id)
        REFERENCES course (course_id)
        ON DELETE CASCADE,

    -- A student cannot register for the same course twice.
    CONSTRAINT uq_student_course
        UNIQUE (student_id, course_id)
);


-- ---------- ATTENDANCE_SESSION ---------------------------------------------
-- A session represents one class period for one course.
-- Business rules 19-21: created by exactly one lecturer for one course.
CREATE TABLE attendance_session (
    session_id   SERIAL    PRIMARY KEY,
    course_id    INTEGER   NOT NULL,
    lecturer_id  INTEGER   NOT NULL,
    session_date DATE      NOT NULL,
    created_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_session_course
        FOREIGN KEY (course_id)
        REFERENCES course (course_id)
        ON DELETE CASCADE,

    CONSTRAINT fk_session_lecturer
        FOREIGN KEY (lecturer_id)
        REFERENCES lecturer (lecturer_id)
        ON DELETE RESTRICT
);


-- ---------- ATTENDANCE_RECORD ----------------------------------------------
-- One row per (session, student): the student's status for that session.
CREATE TABLE attendance_record (
    attendance_id SERIAL      PRIMARY KEY,
    session_id    INTEGER     NOT NULL,
    student_id    INTEGER     NOT NULL,
    status        VARCHAR(10) NOT NULL,
    recorded_at   TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_record_session
        FOREIGN KEY (session_id)
        REFERENCES attendance_session (session_id)
        ON DELETE CASCADE,

    CONSTRAINT fk_record_student
        FOREIGN KEY (student_id)
        REFERENCES student (student_id)
        ON DELETE CASCADE,

    -- Business rule 24: status is either 'Present' or 'Absent', never anything else.
    CONSTRAINT chk_status_value
        CHECK (status IN ('Present', 'Absent')),

    -- Business rule 25: one record per student per session (no duplicates).
    CONSTRAINT uq_session_student
        UNIQUE (session_id, student_id)
);


-- ---------- SYSTEM_SETTING -------------------------------------------------
-- Holds configurable system values. Currently holds the attendance threshold
-- used by reports to flag students as ineligible.
-- Single-row table: always read/update the row with setting_id = 1.
CREATE TABLE system_setting (
    setting_id           SERIAL       PRIMARY KEY,
    attendance_threshold NUMERIC(5,2) NOT NULL DEFAULT 80.00,
    updated_at           TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- Threshold must be a valid percentage between 0 and 100.
    CONSTRAINT chk_threshold_range
        CHECK (attendance_threshold >= 0 AND attendance_threshold <= 100)
);


-- ===========================================================================
-- 3. SEED DATA
-- The minimum data needed to bring the app to life. Nothing else is seeded
-- so that the tables remain clean for real testing.
-- ===========================================================================


-- 3a. The single system-settings row (default threshold = 80%).
INSERT INTO system_setting (attendance_threshold)
VALUES (80.00);


-- 3b. A default administrator account so someone can log in immediately.
--     Username : admin
--     Password : admin123        <-- CHANGE THIS FROM THE APP AFTER FIRST LOGIN
--
-- The string below is the real bcrypt hash of 'admin123'. Bcrypt salts are
-- baked into the hash itself, so this exact string works as-is.
INSERT INTO app_user (username, password_hash, role, status)
VALUES (
    'admin',
    '$2b$12$oRsUcMoGsPKIV7l08LSXQe5CniFTGMWcgYKL/A1Aok0zdFBTihFFS',
    'Administrator',
    'active'
);

INSERT INTO administrator (full_name, email, user_id)
VALUES (
    'System Administrator',
    'admin@pau.edu.ng',
    (SELECT user_id FROM app_user WHERE username = 'admin')
);


-- ===========================================================================
-- DONE. Run  \dt  inside psql to confirm all 11 tables are present.
-- ===========================================================================
