# Lumen ERP - Neumorphic College Management System

A modern, soft-UI (neumorphic) Lumen ERP system built with Flask and SQLAlchemy.

## Features
- **Neumorphic UI**: A beautiful, modern "Soft UI" aesthetic.
- **Role-Based Access Control**: Separate views and permissions for Admin, Faculty, and Student.
- **Attendance Module**: Faculty can mark attendance, and students can view their records.
- **Timetable Module**: Admin can manage schedules; Faculty/Students can view them.
- **Notes & Materials**: Faculty can upload notes (PDF/DOCX) for students to download.

## Installation

1. **Clone the project**
2. **Set up Virtual Environment:**
   ```bash
   py -m venv venv
   .\venv\Scripts\activate
   ```
3. **Install Dependencies:**
   ```bash
   pip install Flask Flask-SQLAlchemy Flask-Login Flask-Migrate Werkzeug
   ```
4. **Initialize Database:**
   ```bash
   # The database is already initialized if you run the app, 
   # but manually you can do:
   python seed_data.py
   ```
5. **Run the App:**
   ```bash
   python app.py
   ```

## Test Accounts
| Role      | Username   | Password   |
|-----------|------------|------------|
| Admin     | admin      | admin123   |
| Faculty   | faculty1   | faculty123 |
| Student   | student1   | student123 |

## Technologies
- Flask
- SQLite (SQLAlchemy)
- CSS3 (Neumorphism)
- Jinja2
