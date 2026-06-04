# SIBAS — Attendance Management System (Group 6)

DTS304: Data Management I — 2025/2026 Second Semester Project
Pan-Atlantic University, School of Science and Technology

A browser-based attendance management system built with **PostgreSQL** (database)
and **Python + Streamlit** (application). Three roles: Administrator, Lecturer, Student.

---

## Tech stack

- **Database:** PostgreSQL
- **Backend:** Python (`psycopg2` / `psycopg`)
- **Frontend:** Streamlit
- **Auth:** hashed passwords (no plaintext, ever)

---

## Project structure

```
sibas_group6/
├── scripts/
│   ├── script1_schema.sql        # DB + table creation (Part 1 deliverable)
│   └── script2_register.py       # Student registration + bulk CSV (Part 2 deliverable)
├── app/
│   ├── db.py                     # Shared DB connection + parameterised query helper
│   ├── auth.py                   # Login, hashing, sessions, RBAC
│   ├── attendance.py             # Sessions, CSV upload, manual override
│   ├── reports.py                # Attendance %, dept/course/student reports, CSV/PDF export
│   └── dashboards/               # Streamlit pages (admin / lecturer / student)
├── data/                         # Sample CSVs for testing
└── README.md
```

> Folders are named by **function**, not by person. Who owns what is in the
> table below — that way reassigning work is a text edit, not a rename that
> breaks every import.

---

## Ownership

| Area                          | File(s)                          | Owner(s)        |
|-------------------------------|----------------------------------|-----------------|
| Business rules, ERD, schema doc | (docs — shared with team)       | Kene            |
| Database schema (Script 1 & 2) | `scripts/`, `app/db.py`         | Munachi + Frank |
| Auth, hashing, RBAC, sessions  | `app/auth.py`                   | Chimdi          |
| Attendance (sessions, CSV, override) | `app/attendance.py`       | Ugo             |
| Frontend dashboards            | `app/dashboards/`               | Alim (+ Munachi on student dashboard) |
| Reports + export + docs        | `app/reports.py`                | Maya + Ebuka    |
| Integration / repo / merging   | (whole repo)                    | Munachi         |

---

## Naming conventions (lock these — everyone follows)

- Tables and columns: `snake_case` (e.g. `attendance_session`, `matric_number`)
- Primary keys: `<table>_id` (e.g. `student_id`, `course_id`)
- Foreign keys: match the PK they reference (e.g. `student_id` in another table)
- Timestamps: `created_at`, `updated_at`
- No spaces, no camelCase, no plurals-vs-singular confusion — pick singular table names.

---

## Git workflow (IMPORTANT — read before pushing)

**Never push directly to `main`.** With 8 people, that's how the codebase breaks.

1. Pull the latest main before starting:
   ```bash
   git checkout main
   git pull origin main
   ```
2. Branch off main for your work (name it `<yourname>-<feature>`):
   ```bash
   git checkout -b chimdi-auth
   ```
3. Commit and push your branch:
   ```bash
   git add .
   git commit -m "Add login + password hashing"
   git push origin chimdi-auth
   ```
4. Open a **Pull Request** on GitHub into `main`.
5. Munachi (integrator) reviews and merges. Branch gets deleted after merge.

If two people edit the same file, the PR review is where we catch and resolve it —
**not** by overwriting each other on main.

---

## Setup (each member, after cloning)

```bash
git clone https://github.com/MUNACHISOHENRY/sibas_group6.git
cd sibas_group6
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

DB credentials go in a local `.env` file (see `.env.example`) — **never commit
real credentials.** The `.gitignore` already excludes `.env`.

---

## Deliverables (due to sadubi@pau.edu.ng ON/BEFORE June 10, 2026)

1. **Script 1** — `scripts/script1_schema.sql`
2. **Script 2** — `scripts/script2_register.py`
3. **Zip** of the full application codebase

Defense: June 11 (CS) / June 12 (SE). Every member must be able to explain their section.