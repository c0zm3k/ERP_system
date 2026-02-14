from datetime import datetime
from extensions import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), index=True, unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    role = db.Column(db.String(20), nullable=False) # Admin, Faculty, Student
    image_file = db.Column(db.String(20), nullable=False, default='default.jpg')
    
    # Relationships
    student_profile = db.relationship('StudentDetails', backref='user', uselist=False, cascade="all, delete-orphan")
    faculty_profile = db.relationship('FacultyDetails', backref='user', uselist=False, cascade="all, delete-orphan")
    leaves = db.relationship('Leaves', backref='user', lazy='dynamic', cascade="all, delete-orphan")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class StudentDetails(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    enrollment_no = db.Column(db.String(20), unique=True, nullable=False)
    course = db.Column(db.String(100), nullable=False)
    department = db.Column(db.String(100), nullable=False, default='General')
    class_name = db.Column(db.String(50), nullable=False, default='A')
    semester = db.Column(db.Integer, nullable=False)
    
    attendances = db.relationship('Attendance', backref='student', lazy='dynamic', cascade="all, delete-orphan")

class FacultyDetails(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    department = db.Column(db.String(100), nullable=False)
    designation = db.Column(db.String(100), nullable=False)
    
    timetable_slots = db.relationship('Timetable', backref='faculty', lazy='dynamic', cascade="all, delete-orphan")

class Attendance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False, default=datetime.utcnow)
    student_id = db.Column(db.Integer, db.ForeignKey('student_details.id'), nullable=False)
    status = db.Column(db.String(10), nullable=False) # Present, Absent
    subject = db.Column(db.String(100), nullable=False)

class Timetable(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    day = db.Column(db.String(10), nullable=False) # Monday, Tuesday, etc.
    time_slot = db.Column(db.String(50), nullable=False) 
    subject = db.Column(db.String(100), nullable=False)
    class_name = db.Column(db.String(50), nullable=False, default='General')
    faculty_id = db.Column(db.Integer, db.ForeignKey('faculty_details.id'), nullable=True)

class Leaves(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    reason = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), nullable=False, default='Pending') # Pending, Approved, Rejected
    date_submitted = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

class ClassAllotment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    faculty_id = db.Column(db.Integer, db.ForeignKey('faculty_details.id'), nullable=False)
    department = db.Column(db.String(100), nullable=False)
    class_name = db.Column(db.String(50), nullable=False)
    subject = db.Column(db.String(100), nullable=False)
    
    faculty = db.relationship('FacultyDetails', backref=db.backref('allotments', lazy='dynamic', cascade="all, delete-orphan"))
