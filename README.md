# Lumen ERP

A modern, neumorphic (soft-UI) college management system built with Flask and SQLAlchemy. It provides role-based dashboards for **Admin**, **HOD**, **Asst. HOD**, **Faculty**, and **Student**, with modules for attendance, leaves, fees, certificates, events, and class allotment.

---

## Features

### Access control
- **Role-based access:** Admin, HOD, Asst. HOD, Faculty, Student
- **Authentication:** Flask-Login session management
- **Hierarchy:** Faculty under department HOD/Asst. HOD; students under HOD

### Modules
- **Dashboard** – Role-specific home with quick links
- **Attendance** – Faculty mark attendance by class/subject; students view records
- **Leaves** – Request and approve leaves (Faculty → HOD → Admin; Student → Faculty → HOD)
- **Fees** – Admin adds fees; students view and pay
- **Certificates** – Admin uploads; students view and download
- **Notes / Digital library** – Faculty upload materials; students download
- **Calendar** – Admin adds events; all view
- **User management** – Admin creates HOD/Asst. HOD (with department) and Faculty (department dropdown, auto-assigned to department HOD)
- **HOD panel** – Register students, view department faculty/students, class allotment
- **Class allotment** – HOD assigns faculty to class/subject

### Tech stack
- **Backend:** Python 3, Flask
- **Database:** SQLite (default), SQLAlchemy ORM, Flask-Migrate
- **Frontend:** HTML5, CSS3 (neumorphism), Jinja2
- **Auth:** Flask-Login

---

## Project structure

```
ERP_system/
├── app.py              # Application factory & entry point
├── config.py           # Configuration (secret, DB URL, upload folder)
├── extensions.py       # Flask extensions (db, login_manager, migrate)
├── models.py           # SQLAlchemy models
├── utils.py            # Decorators (e.g. role_required)
├── init_db.py          # Reset DB and seed default admin
├── requirements.txt
├── routes/
│   ├── __init__.py
│   ├── auth.py         # Login, logout, index
│   ├── main.py         # Dashboard, attendance, leaves, fees, certificates, notes, calendar
│   ├── admin.py        # Admin panel, user management, add fee/certificate/event
│   └── hod.py         # HOD panel, student registration, class allotment
├── templates/          # Jinja2 HTML
├── static/
│   ├── css/
│   └── uploads/        # Notes and certificates
├── instance/           # SQLite DB (created at run time)
└── README.md
```

---

## Getting started

### Prerequisites
- Python 3.8+
- pip

### Setup

1. **Clone and enter the project**
   ```bash
   git clone <your-repo-url>
   cd ERP_system
   ```

2. **Create and activate a virtual environment**
   - Windows:
     ```bash
     py -m venv venv
     .\venv\Scripts\activate
     ```
   - macOS / Linux:
     ```bash
     python3 -m venv venv
     source venv/bin/activate
     ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Optional: reset database and seed admin**
   ```bash
   python init_db.py
   ```
   This recreates the DB and adds a default admin (`admin` / `admin123`). If you skip this, the app will create tables and the admin user on first run.

5. **Run the app**
   ```bash
   python app.py
   ```
   Open **http://127.0.0.1:5000** (or the port shown in the terminal).

### Environment (optional)
- `SECRET_KEY` – Flask secret (defaults to a dev key if unset)
- `DATABASE_URL` – DB URL (default: `sqlite:///college.db` in `instance/`)
- `PORT` – Server port (default: 5000)

---

## Test accounts

After running `init_db.py` or first run:

| Role    | Username | Password   | Notes                    |
|---------|----------|------------|---------------------------|
| Admin   | `admin`  | `admin123` | Full access, user management |
| Faculty | Create via Admin → User Management (select department) |
| Student | Create via HOD Panel (HOD’s department)                |

Create at least one **HOD** (or Asst. HOD) with a department so that department appears in the faculty-creation dropdown and faculty can be auto-assigned.

---

## License and contributing

Use and adapt as needed for your project. Contributions (issues, docs, code) are welcome.
