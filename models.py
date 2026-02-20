from datetime import datetime
from extensions import db
from flask_login import UserMixin # Keeping for now to avoid breaking existing logic during migration
from werkzeug.security import generate_password_hash, check_password_hash

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), index=True, unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    # Roles: Admin, HOD, Asst_HOD, Faculty, Student
    role = db.Column(db.String(20), nullable=False) 
    image_file = db.Column(db.String(20), nullable=False, default='default.jpg')
    
    # Leave Tracking
    total_leaves = db.Column(db.Integer, default=30)
    leaves_taken = db.Column(db.Integer, default=0)
    
    # Hierarchy
    department = db.Column(db.String(100), nullable=True) # For HOD/Faculty/Students
    
    # Relationships
    student_profile = db.relationship('StudentDetails', backref='user', uselist=False, cascade="all, delete-orphan")
    faculty_profile = db.relationship('FacultyDetails', backref='user', uselist=False, cascade="all, delete-orphan")
    hod_profile = db.relationship('HODDetails', backref='user', uselist=False, cascade="all, delete-orphan")
    leaves = db.relationship('Leaves', backref='user', lazy='dynamic', cascade="all, delete-orphan")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class HODDetails(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    department = db.Column(db.String(100), nullable=False)
    rank = db.Column(db.String(20), default='HOD') # HOD, Asst_HOD
    
    # Managed Entities
    faculties = db.relationship('FacultyDetails', backref='hod', lazy='dynamic')
    students = db.relationship('StudentDetails', backref='hod', lazy='dynamic')

class FacultyDetails(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    department = db.Column(db.String(100), nullable=False)
    designation = db.Column(db.String(100), nullable=False)
    hod_id = db.Column(db.Integer, db.ForeignKey('hod_details.id'), nullable=True)
    
    assigned_students = db.relationship('StudentDetails', backref='faculty_advisor', lazy='dynamic')

class StudentDetails(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    enrollment_no = db.Column(db.String(20), unique=True, nullable=False)
    course = db.Column(db.String(100), nullable=False)
    department = db.Column(db.String(100), nullable=False, default='General')
    class_name = db.Column(db.String(50), nullable=False, default='A')
    semester = db.Column(db.Integer, nullable=False)
    
    # Assignment
    hod_id = db.Column(db.Integer, db.ForeignKey('hod_details.id'), nullable=True)
    faculty_id = db.Column(db.Integer, db.ForeignKey('faculty_details.id'), nullable=True)
    
    attendances = db.relationship('Attendance', backref='student', lazy='dynamic', cascade="all, delete-orphan")

class Attendance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False, default=datetime.utcnow)
    student_id = db.Column(db.Integer, db.ForeignKey('student_details.id'), nullable=False)
    status = db.Column(db.String(10), nullable=False) # Present, Absent
    subject = db.Column(db.String(100), nullable=False)

class Leaves(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    type = db.Column(db.String(50), nullable=False, default='Casual') # Casual, Medical, Other
    reason = db.Column(db.Text, nullable=False)
    start_date = db.Column(db.Date, nullable=False, default=datetime.utcnow)
    end_date = db.Column(db.Date, nullable=False, default=datetime.utcnow)
    
    # Workflow Statuses: 
    # Student: Pending_Faculty -> Pending_HOD -> Approved
    # Faculty: Pending_HOD -> Pending_Admin -> Approved
    # HOD: Pending_Admin -> Approved
    # Others: Rejected, Revoked
    status = db.Column(db.String(50), nullable=False, default='Pending') 
    
    date_submitted = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    
class Event(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    event_date = db.Column(db.Date, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Fee(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student_details.id'), nullable=False)
    title = db.Column(db.String(100), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    due_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), nullable=False, default='Unpaid')
    semester = db.Column(db.Integer, nullable=False)
    
    student = db.relationship('StudentDetails', backref=db.backref('fees', lazy='dynamic', cascade="all, delete-orphan"))

class Certificate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student_details.id'), nullable=False)
    title = db.Column(db.String(100), nullable=False)
    file_path = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    date_uploaded = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    student = db.relationship('StudentDetails', backref=db.backref('certificates', lazy='dynamic', cascade="all, delete-orphan"))

class TimeSlot(db.Model):
    """Time slots for classes (e.g. Mon 9-10, Tue 11-12). Created by HOD per department."""
    id = db.Column(db.Integer, primary_key=True)
    hod_id = db.Column(db.Integer, db.ForeignKey('hod_details.id'), nullable=False)
    name = db.Column(db.String(80), nullable=False)  # e.g. "Slot 1", "Mon 9-10"
    day_of_week = db.Column(db.String(20), nullable=False)  # Mon, Tue, Wed, Thu, Fri, Sat
    start_time = db.Column(db.String(10), nullable=False)  # "09:00"
    end_time = db.Column(db.String(10), nullable=False)    # "10:00"
    department = db.Column(db.String(100), nullable=False)

    hod = db.relationship('HODDetails', backref=db.backref('time_slots', lazy='dynamic', cascade="all, delete-orphan"))
    allotments = db.relationship('ClassAllotment', backref='slot', lazy='dynamic', foreign_keys='ClassAllotment.slot_id')


class ClassAllotment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    faculty_id = db.Column(db.Integer, db.ForeignKey('faculty_details.id'), nullable=False)
    faculty_name = db.Column(db.String(100), nullable=True)
    department = db.Column(db.String(100), nullable=False)
    course = db.Column(db.String(100), nullable=True)       # e.g. B.Tech CS - must match StudentDetails.course
    semester = db.Column(db.Integer, nullable=True)          # must match StudentDetails.semester
    class_name = db.Column(db.String(50), nullable=False)    # section e.g. A, I-CS
    subject = db.Column(db.String(100), nullable=False)
    slot_id = db.Column(db.Integer, db.ForeignKey('time_slot.id'), nullable=True)

    faculty = db.relationship('FacultyDetails', backref=db.backref('allotments', lazy='dynamic', cascade="all, delete-orphan"))


class ClassAllotmentRequest(db.Model):
    """When HOD wants to assign a faculty from another department, they create a request for that dept's HOD."""
    id = db.Column(db.Integer, primary_key=True)
    requesting_hod_id = db.Column(db.Integer, db.ForeignKey('hod_details.id'), nullable=False)
    faculty_id = db.Column(db.Integer, db.ForeignKey('faculty_details.id'), nullable=False)
    department = db.Column(db.String(100), nullable=False)
    course = db.Column(db.String(100), nullable=True)
    semester = db.Column(db.Integer, nullable=True)
    class_name = db.Column(db.String(50), nullable=False)
    subject = db.Column(db.String(100), nullable=False)
    slot_id = db.Column(db.Integer, db.ForeignKey('time_slot.id'), nullable=True)
    status = db.Column(db.String(30), nullable=False, default='Pending')  # Pending, Approved, Rejected
    responding_hod_id = db.Column(db.Integer, db.ForeignKey('hod_details.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    requesting_hod = db.relationship('HODDetails', foreign_keys=[requesting_hod_id])
    responding_hod = db.relationship('HODDetails', foreign_keys=[responding_hod_id])
    faculty = db.relationship('FacultyDetails', backref='allotment_requests_received')

class Broadcast(db.Model):
    """Broadcast messages for institution-wide (Admin) or department-specific (HOD) announcements."""
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    scope = db.Column(db.String(20), nullable=False)  # 'institution' for Admin, 'department' for HOD
    department = db.Column(db.String(100), nullable=True)  # Only set if scope is 'department'
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_pinned = db.Column(db.Boolean, default=False)
    
    created_by = db.relationship('User', backref=db.backref('broadcasts', lazy='dynamic'))

    def __repr__(self):
        return f'<Broadcast {self.title}>'