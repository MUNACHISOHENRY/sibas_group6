# SIBAS — Attendance Management System (Group 6)

DTS304: Data Management I — 2025/2026 Second Semester Project
Pan-Atlantic University, School of Science and Technology

A browser-based attendance management system built with **PostgreSQL** and
**Python + Streamlit**. Three roles: Administrator, Lecturer, Student.

> **Current status:** Database is built (Scripts 1 & 2 done). Auth, attendance,
> reports, and frontend are in progress. See "Who's working on what" below.

---

## ⚡ Quick start (do this once)

Run these in order from the repo folder. PowerShell is fine.

```powershell
# 1. Install all Python dependencies
pip install -r requirements.txt

# 2. Set up your local DB credentials
Copy-Item .env.example .env
#    Now open .env in a text editor and replace 'your_local_password_here'
#    with your actual PostgreSQL password.

# 3. Build the database (creates 'sibas' DB, all tables, default admin)
psql -U postgres -f scripts/script1_schema.sql

# 4. (Optional) Seed test data so you can play with the app
psql -U postgres -d sibas -f data/test_setup.sql
python scripts/script2_register.py --csv data/sample_students.csv

# 5. Test that your Python can talk to the database
python app/db.py
```

If step 5 prints **"Connected to PostgreSQL successfully"** — you're set.
If anything errors, see [Troubleshooting](#-troubleshooting) at the bottom.

---

## 🔑 Default login

After step 3 above, you can log in to the app with:

| Role          | Username    | Password      |
|---------------|-------------|---------------|
| Administrator | `admin`     | `admin123`    |
| Lecturer      | `lecturer1` | `Lecturer123` | *(only if you ran step 4)*

> Change these from the app after first login — don't ship defaults to defense.

---

## 👥 Who's working on what

Each person owns a specific file. **Stay in your own file** to avoid stepping
on each other's work.

| Person       | File / Folder                       | Task                                                     |
|--------------|-------------------------------------|----------------------------------------------------------|
| **Kene**     | (docs — shared with team)           | Business rules, ER diagram, schema mapping doc           |
| **Munachi**  | `scripts/`, `app/db.py`, `app/dashboards/student.py` | Database + integration + student dashboard |
| **Frank**    | `scripts/`                          | Database (co-owner with Munachi)                         |
| **Chimdi**   | `app/auth.py`                       | Login, password hashing, sessions, role-based access     |
| **Ugo**      | `app/attendance.py`                 | Attendance sessions, CSV upload, manual override         |
| **Alim**     | `app/dashboards/admin.py`, `app/dashboards/lecturer.py` | Admin + lecturer dashboards (Streamlit UI) |
| **Maya**     | `app/reports.py`                    | Attendance %, dept/course/student reports, CSV export    |
| **Ebuka**    | `app/reports.py`, documentation     | PDF export, eligibility flag (co-owner with Maya) + docs |

### What each file should do (brief)

- `app/db.py` — **Done.** Shared DB connection. Everyone imports `run_query`, `run_query_one`, `run_command`, `run_command_returning` from this.
- `app/auth.py` — Functions: `login(username, password)`, `logout()`, `current_user()`, `require_role(role)`. Uses bcrypt to verify hashed passwords.
- `app/attendance.py` — Functions: `create_session(...)`, `upload_attendance_csv(...)`, `override_attendance(...)`. CSV must reject any status outside `Present`/`Absent`.
- `app/reports.py` — Functions: `attendance_percentage(student_id, course_id)`, `department_report(...)`, `course_report(...)`, `student_report(...)`, `export_csv(...)`, `export_pdf(...)`. Reads threshold from `system_setting` table.
- `app/dashboards/admin.py` / `lecturer.py` / `student.py` — Streamlit pages. Each calls the relevant backend functions and respects role-based access.

---

## 🔁 Daily workflow

The whole team works on `main`. Each person edits their own file. That means
no branches needed — but you must pull before starting and push when done.

**Using GitHub Desktop (recommended):**

1. Click **"Fetch origin"** then **"Pull"** to get everyone's latest work.
2. Open the file you own in your editor. Make your changes.
3. Back in GitHub Desktop, type a short message (e.g. "Add login function").
4. Click **"Commit to main"**.
5. Click **"Push origin"** to upload.

**Using the command line:**

```powershell
git pull origin main         # before you start
# ... edit your file ...
git add .
git commit -m "Add login function"
git push origin main         # when done
```

**Stuck on git?** Send Munachi your file directly (WhatsApp/email) and he'll
commit it for you. Don't let git block you from making progress.

---

## 📁 Project structure

```
sibas_group6/
├── scripts/
│   ├── script1_schema.sql       ✅ done — full database schema
│   └── script2_register.py      ✅ done — student registration + bulk CSV
├── app/
│   ├── db.py                    ✅ done — shared DB connection layer
│   ├── auth.py                  ⏳ in progress (Chimdi)
│   ├── attendance.py            ⏳ in progress (Ugo)
│   ├── reports.py               ⏳ in progress (Maya + Ebuka)
│   └── dashboards/
│       ├── admin.py             ⏳ Alim
│       ├── lecturer.py          ⏳ Alim
│       └── student.py           ⏳ Munachi
├── data/
│   ├── test_setup.sql           test data (department, programme, lecturer, courses)
│   └── sample_students.csv      sample CSV for bulk registration
├── .env.example                 template for DB credentials
├── .gitignore
├── requirements.txt
└── README.md                    (this file)
```

---

## 📋 Conventions

- **Tables and columns:** `snake_case` (e.g. `attendance_session`, `matric_no`)
- **Primary keys:** `<table>_id` (e.g. `student_id`, `course_id`)
- **Database queries:** always use parameterised queries through `app/db.py`.
  Never write `f"SELECT ... WHERE id = {x}"` — that's SQL injection.
  Always do: `run_query("SELECT ... WHERE id = %s", (x,))`
- **Passwords:** hashed with bcrypt before storing. Never plain text.

---

## 📦 Deliverables

Due to **sadubi@pau.edu.ng** on or before **June 10, 2026**:

1. `scripts/script1_schema.sql`
2. `scripts/script2_register.py`
3. Zip of the full codebase

**Defense:** June 11 (Computer Science) / June 12 (Software Engineering).

> 10 of 15 defense marks come from **3 randomly chosen members** answering
> the instructor's questions. Everyone must be able to explain their section
> out loud. We'll do a full walkthrough before defense.

---

## 🩹 Troubleshooting

**`'psql' is not recognized`**
PostgreSQL isn't in your PATH. Either add it to PATH, or use the full path
to psql, something like:
`"C:\Program Files\PostgreSQL\17\bin\psql.exe" -U postgres ...`

**`password authentication failed for user "postgres"`**
Wrong password for the `postgres` superuser. Use the password you set when
you installed PostgreSQL. If you've forgotten it, you'll need to reset it
via pgAdmin or reinstall.

**`ModuleNotFoundError: No module named 'psycopg2'` (or `bcrypt`, `streamlit`...)**
You didn't run `pip install -r requirements.txt`. Do it now.

**`ModuleNotFoundError: No module named 'app'`**
You're running a script from inside the wrong folder. Always run commands
from the **repo root** (`sibas_group6/`), not from inside `scripts/`.

**`database "sibas" already exists`**
The script normally drops and recreates it. If you see this, your psql
session might be open and holding a lock. Close all psql/pgAdmin windows
connected to `sibas`, then re-run.

**`.env file not found` or DB connects with wrong details**
You skipped `Copy-Item .env.example .env`. Do that and edit `.env` with
your real Postgres password.

**`pip` itself isn't recognized**
Python isn't on PATH. Either reinstall Python (tick "Add to PATH"), or
use `py -m pip install -r requirements.txt`.

**Anything else** — drop a screenshot in the group chat. Don't suffer alone.