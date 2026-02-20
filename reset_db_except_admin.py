"""Reset all database data except Admin user(s). Run with: python reset_db_except_admin.py"""
from app import create_app
from extensions import db

app = create_app()

with app.app_context():
    from models import (
        ClassAllotmentRequest, ClassAllotment, TimeSlot, Attendance,
        Fee, Certificate, Leaves, Event, StudentDetails, FacultyDetails,
        HODDetails, User
    )

    # Delete in dependency order to avoid FK violations
    ClassAllotmentRequest.query.delete()
    ClassAllotment.query.delete()
    TimeSlot.query.delete()
    Attendance.query.delete()
    Fee.query.delete()
    Certificate.query.delete()
    Leaves.query.delete()
    Event.query.delete()
    StudentDetails.query.delete()
    FacultyDetails.query.delete()
    HODDetails.query.delete()

    # Remove all non-Admin users
    User.query.filter(User.role != 'Admin').delete()

    db.session.commit()
    admin_count = User.query.filter_by(role='Admin').count()
    print(f"Database reset complete. {admin_count} Admin user(s) retained. All other data removed.")
    print("Login with admin / admin123")
