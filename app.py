from flask import Flask, render_template, redirect, url_for, flash, request, send_from_directory
from config import Config
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_migrate import Migrate
from functools import wraps
import os
from werkzeug.utils import secure_filename
from datetime import datetime

from extensions import db, login_manager, migrate

def role_required(role):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated or current_user.role != role:
                flash('You do not have permission to access this page.', 'danger')
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)

    from models import User

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    with app.app_context():
        # Ensure instance folder exists for SQLite
        if not os.path.exists(app.instance_path):
            os.makedirs(app.instance_path)
            
        db.create_all()
        
        # Seed default admin if missing
        if not User.query.filter_by(role='Admin').first():
            admin = User(username='admin', role='Admin')
            admin.set_password('admin123')
            db.session.add(admin)
            db.session.commit()

        # Ensure upload folder exists
        if not os.path.exists(app.config['UPLOAD_FOLDER']):
            os.makedirs(app.config['UPLOAD_FOLDER'])

    @app.route('/')
    def index():
        return redirect(url_for('login'))

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if current_user.is_authenticated:
            return redirect(url_for('dashboard'))
        if request.method == 'POST':
            username = request.form.get('username')
            password = request.form.get('password')
            user = User.query.filter_by(username=username).first()
            if user and user.check_password(password):
                login_user(user)
                flash('Logged in successfully!', 'success')
                return redirect(url_for('dashboard'))
            else:
                flash('Invalid username or password', 'danger')
        return render_template('login.html')

    @app.route('/logout')
    @login_required
    def logout():
        logout_user()
        flash('Logged out successfully!', 'info')
        return redirect(url_for('login'))

    @app.route('/dashboard')
    @login_required
    def dashboard():
        allotments = []
        if current_user.role == 'Faculty':
            allotments = current_user.faculty_profile.allotments.all()
        return render_template('dashboard.html', allotments=allotments)

    @app.route('/attendance', methods=['GET', 'POST'])
    @login_required
    @role_required('Faculty')
    def mark_attendance():
        from models import StudentDetails, Attendance, ClassAllotment
        faculty = current_user.faculty_profile
        allotments = faculty.allotments.all()
        
        selected_allotment_id = request.args.get('allotment_id', type=int)
        date_str = request.args.get('date')
        
        if not date_str:
            date_obj = datetime.utcnow().date()
            date_str = date_obj.strftime('%Y-%m-%d')
        else:
            try:
                date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                date_obj = datetime.utcnow().date()
                date_str = date_obj.strftime('%Y-%m-%d')

        selected_allotment = None
        students = []
        marked_status = {}
        
        if selected_allotment_id:
            selected_allotment = ClassAllotment.query.get(selected_allotment_id)
            if selected_allotment and selected_allotment.faculty_id == faculty.id:
                students = StudentDetails.query.filter_by(
                    department=selected_allotment.department,
                    class_name=selected_allotment.class_name
                ).all()
                
                # Fetch existing attendance for this date and subject
                existing_attendance = Attendance.query.filter_by(
                    date=date_obj,
                    subject=selected_allotment.subject
                ).filter(Attendance.student_id.in_([s.id for s in students])).all()
                
                marked_status = {a.student_id: a.status for a in existing_attendance}
                
        # Calculate counts
        present_count = list(marked_status.values()).count('Present')
        absent_count = list(marked_status.values()).count('Absent')

        if request.method == 'POST':
            allotment_id = request.form.get('allotment_id', type=int)
            allotment = ClassAllotment.query.get(allotment_id)
            if not allotment or allotment.faculty_id != faculty.id:
                flash('Invalid allotment.', 'danger')
                return redirect(url_for('mark_attendance'))

            post_date_str = request.form.get('date')
            post_date_obj = datetime.strptime(post_date_str, '%Y-%m-%d').date() if post_date_str else datetime.utcnow().date()
            subject = allotment.subject
            
            students_to_mark = StudentDetails.query.filter_by(
                department=allotment.department,
                class_name=allotment.class_name
            ).all()

            for student in students_to_mark:
                status = request.form.get(f'status_{student.id}')
                if status:
                    existing = Attendance.query.filter_by(student_id=student.id, date=post_date_obj, subject=subject).first()
                    if existing:
                        existing.status = status
                    else:
                        att = Attendance(student_id=student.id, date=post_date_obj, status=status, subject=subject)
                        db.session.add(att)
            db.session.commit()
            flash(f'Attendance for {allotment.class_name} ({allotment.subject}) updated!', 'success')
            return redirect(url_for('dashboard'))
            
        return render_template('attendance.html', students=students, today=date_str, 
                               allotments=allotments, selected_allotment=selected_allotment,
                               marked_status=marked_status, present_count=present_count, absent_count=absent_count)


    @app.route('/my_attendance')
    @login_required
    @role_required('Student')
    def view_attendance():
        from models import Attendance
        attendances = Attendance.query.filter_by(student_id=current_user.student_profile.id).all()
        
        present_count = sum(1 for a in attendances if a.status == 'Present')
        absent_count = sum(1 for a in attendances if a.status == 'Absent')
        
        return render_template('view_attendance.html', 
                               attendances=attendances, 
                               present=present_count, 
                               absent=absent_count)

    @app.route('/leaves', methods=['GET', 'POST'])
    @login_required
    def leaves():
        from models import Leaves, User
        if request.method == 'POST':
            leave_type = request.form.get('type') # Casual, Medical, Other
            reason = request.form.get('reason')
            start_date = datetime.strptime(request.form.get('start_date'), '%Y-%m-%d').date()
            end_date = datetime.strptime(request.form.get('end_date'), '%Y-%m-%d').date()
            
            # Initial status depends on role
            if current_user.role == 'Student':
                initial_status = 'Pending_Faculty'
            elif current_user.role == 'Faculty':
                initial_status = 'Pending_HOD'
            elif current_user.role == 'HOD':
                initial_status = 'Pending_Admin'
            else:
                initial_status = 'Approved' # Admin leaves are auto-approved for now or handle differently
                
            new_leave = Leaves(user_id=current_user.id, type=leave_type, reason=reason, 
                               start_date=start_date, end_date=end_date, status=initial_status)
            db.session.add(new_leave)
            db.session.commit()
            flash('Leave request initialized and routed for approval!', 'success')
            return redirect(url_for('leaves'))
        
        # Dashboard leave stats
        leaves_left = current_user.total_leaves - current_user.leaves_taken
        
        # Viewing logic
        if current_user.role == 'Admin':
            # Admin sees HOD leaves (Pending_Admin) and Faculty leaves (Pending_Admin) 
            # and potentially proxy for HOD if HOD is on leave (simplifying: Admin sees all final stages)
            all_leaves = Leaves.query.filter(Leaves.status.in_(['Pending_Admin', 'Approved', 'Rejected'])).all()
        elif current_user.role == 'HOD':
            # HOD sees Student leaves (Pending_HOD) and Faculty leaves (Pending_HOD)
            # Also as Asst HOD proxy? Assuming Asst HOD has role HOD but check HODDetails.rank
            all_leaves = Leaves.query.filter(Leaves.status.in_(['Pending_HOD', 'Pending_Admin'])).all()
        elif current_user.role == 'Faculty':
            # Faculty sees Student leaves (Pending_Faculty)
            all_leaves = Leaves.query.filter(Leaves.status.in_(['Pending_Faculty', 'Pending_HOD'])).all()
        else:
            all_leaves = current_user.leaves.all()
            
        return render_template('leaves.html', leaves=all_leaves, left=leaves_left)

    @app.route('/leaves/approve/<int:id>')
    @login_required
    def approve_leave(id):
        from models import Leaves, User
        leave = Leaves.query.get_or_404(id)
        requester = leave.user
        
        # Simple Proxy Authority: If HOD rank is Asst_HOD and Admin is not available
        # we can check current_user.role and rank.
        
        if current_user.role == 'Faculty' and leave.status == 'Pending_Faculty':
            leave.status = 'Pending_HOD'
            flash('Level 1 approval complete! Routed to HOD.', 'success')
        elif current_user.role == 'HOD' and leave.status == 'Pending_HOD':
            if requester.role == 'Student':
                leave.status = 'Approved'
                requester.leaves_taken += (leave.end_date - leave.start_date).days + 1
            else: # Requester is Faculty
                leave.status = 'Pending_Admin'
            flash('Departmental approval complete!', 'success')
        elif (current_user.role == 'Admin' or (current_user.role == 'HOD' and current_user.hod_profile.rank == 'Asst_HOD')) and leave.status == 'Pending_Admin':
            leave.status = 'Approved'
            requester.leaves_taken += (leave.end_date - leave.start_date).days + 1
            flash('Leave fully authorized!', 'success')
        else:
            flash('Unauthorized or invalid flow.', 'danger')
            
        db.session.commit()
        return redirect(url_for('leaves'))

    @app.route('/leaves/reject/<int:id>')
    @login_required
    def reject_leave(id):
        from models import Leaves
        leave = Leaves.query.get_or_404(id)
        leave.status = 'Rejected'
        db.session.commit()
        flash('Leave request denied.', 'warning')
        return redirect(url_for('leaves'))

    @app.route('/fees')
    @login_required
    def view_fees():
        from models import Fee, StudentDetails
        if current_user.role == 'Student':
            fees = current_user.student_profile.fees.all()
        elif current_user.role == 'Admin':
            fees = Fee.query.all()
        else:
            fees = []
        return render_template('fees.html', fees=fees)

    @app.route('/admin/fees/add', methods=['POST'])
    @login_required
    @role_required('Admin')
    def add_fee():
        from models import Fee, StudentDetails
        student_id = request.form.get('student_id')
        title = request.form.get('title')
        amount = request.form.get('amount')
        due_date = datetime.strptime(request.form.get('due_date'), '%Y-%m-%d').date()
        semester = request.form.get('semester')
        
        new_fee = Fee(student_id=student_id, title=title, amount=amount, due_date=due_date, semester=semester)
        db.session.add(new_fee)
        db.session.commit()
        flash('Fee record created!', 'success')
        return redirect(url_for('view_fees'))

    @app.route('/certificates')
    @login_required
    def view_certificates():
        from models import Certificate
        if current_user.role == 'Student':
            certs = current_user.student_profile.certificates.all()
        elif current_user.role == 'Admin':
            certs = Certificate.query.all()
        else:
            certs = []
        return render_template('certificates.html', certificates=certs)

    @app.route('/admin/certificates/upload', methods=['POST'])
    @login_required
    @role_required('Admin')
    def upload_certificate():
        from models import Certificate, StudentDetails
        if 'file' not in request.files:
            flash('No file part', 'danger')
            return redirect(request.url)
        file = request.files['file']
        if file.filename == '':
            flash('No selected file', 'danger')
            return redirect(request.url)
        
        student_id = request.form.get('student_id')
        title = request.form.get('title')
        category = request.form.get('category')
        
        if file:
            filename = secure_filename(file.filename)
            upload_path = os.path.join(app.config['UPLOAD_FOLDER'], 'certificates', filename)
            if not os.path.exists(os.path.dirname(upload_path)):
                os.makedirs(os.path.dirname(upload_path))
            file.save(upload_path)
            
            new_cert = Certificate(student_id=student_id, title=title, category=category, file_path=filename)
            db.session.add(new_cert)
            db.session.commit()
            flash('Certificate uploaded!', 'success')
            
        return redirect(url_for('view_certificates'))

    @app.route('/notes', methods=['GET', 'POST'])
    @login_required
    def notes():
        # Both Faculty and Students can see notes. Only Faculty can upload.
        files = os.listdir(app.config['UPLOAD_FOLDER'])
        # Filter for actual files, ignore .gitkeep or similar if any
        notes_list = [f for f in files if os.path.isfile(os.path.join(app.config['UPLOAD_FOLDER'], f))]
        
        if request.method == 'POST' and current_user.role == 'Faculty':
            if 'file' not in request.files:
                flash('No file part', 'danger')
                return redirect(request.url)
            file = request.files['file']
            if file.filename == '':
                flash('No selected file', 'danger')
                return redirect(request.url)
            if file:
                filename = secure_filename(file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                flash('File uploaded successfully!', 'success')
                return redirect(url_for('notes'))
                
        return render_template('notes.html', notes=notes_list)

    @app.route('/download/<filename>')
    @login_required
    def download_file(filename):
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

    @app.route('/calendar')
    @login_required
    def calendar():
        from models import Event
        all_events = Event.query.order_by(Event.event_date.asc()).all()
        return render_template('calendar.html', events=all_events)

    @app.route('/admin/events/add', methods=['POST'])
    @login_required
    @role_required('Admin')
    def add_event():
        from models import Event
        title = request.form.get('title')
        description = request.form.get('description')
        event_date_str = request.form.get('event_date')
        
        if not title or not event_date_str:
            flash('Error: Missing required fields', 'danger')
            return redirect(url_for('calendar'))
            
        event_date = datetime.strptime(event_date_str, '%Y-%m-%d').date()
        new_event = Event(title=title, description=description, event_date=event_date)
        db.session.add(new_event)
        db.session.commit()
        flash('Event added!', 'success')
        return redirect(url_for('calendar'))

    @app.route('/hod', methods=['GET', 'POST'])
    @login_required
    @role_required('HOD')
    def hod_panel():
        from models import User, StudentDetails, FacultyDetails, Leaves, HODDetails
        hod = current_user.hod_profile
        
        if request.method == 'POST' and 'enrollment_no' in request.form:
            # Add Student Logic
            username = request.form.get('username')
            password = request.form.get('password')
            enrollment = request.form.get('enrollment_no')
            course = request.form.get('course')
            semester = request.form.get('semester')
            
            if User.query.filter_by(username=username).first():
                flash('Username already exists', 'danger')
                return redirect(url_for('hod_panel'))
                
            new_student = User(username=username, role='Student', department=hod.department)
            new_student.set_password(password)
            db.session.add(new_student)
            db.session.flush()
            
            student = StudentDetails(user_id=new_student.id, enrollment_no=enrollment, 
                                    course=course, department=hod.department, 
                                    semester=semester, hod_id=hod.id)
            db.session.add(student)
            db.session.commit()
            flash('Student registered within department!', 'success')
            return redirect(url_for('hod_panel'))

        stats = {
            'total_students': hod.students.count(),
            'total_faculty': hod.faculties.count(),
            'pending_leaves': Leaves.query.filter_by(status='Pending_HOD').count(),
        }
        dept_faculty = hod.faculties.all()
        dept_students = hod.students.all()
        
        return render_template('hod_panel.html', stats=stats, faculty=dept_faculty, students=dept_students)

    @app.route('/admin')
    @login_required
    @role_required('Admin')
    def admin_panel():
        from models import User, StudentDetails, FacultyDetails, Leaves, Fee, HODDetails
        stats = {
            'total_users': User.query.count(),
            'total_students': StudentDetails.query.count(),
            'total_faculty': FacultyDetails.query.count(),
            'pending_leaves': Leaves.query.filter_by(status='Pending_Admin').count(),
            'total_revenue': db.session.query(db.func.sum(Fee.amount)).filter(Fee.status == 'Paid').scalar() or 0
        }
        
        # Sorted Faculty Registry
        # Logic: HOD -> Asst_HOD -> Faculty, grouped by Department
        all_faculty = FacultyDetails.query.join(User).order_by(User.department.asc()).all()
        all_hods = HODDetails.query.join(User).order_by(User.department.asc(), HODDetails.rank.asc()).all()
        
        return render_template('admin_panel.html', stats=stats, faculty=all_faculty, hods=all_hods)

    @app.route('/admin/users', methods=['GET', 'POST'])
    @login_required
    @role_required('Admin')
    def manage_users():
        from models import User, StudentDetails, FacultyDetails, HODDetails
        if request.method == 'POST':
            username = request.form.get('username')
            password = request.form.get('password')
            role = request.form.get('role')
            
            if role == 'Student':
                flash('Students must be registered by HODs.', 'danger')
                return redirect(url_for('manage_users'))

            if User.query.filter_by(username=username).first():
                flash('Username already exists', 'danger')
                return redirect(url_for('manage_users'))
                
            new_user = User(username=username, role=role)
            new_user.set_password(password)
            db.session.add(new_user)
            db.session.flush()
            
            if role == 'Faculty':
                dept = request.form.get('faculty_department')
                desig = request.form.get('designation')
                hod_id = request.form.get('hod_id')
                faculty = FacultyDetails(user_id=new_user.id, department=dept, designation=desig, hod_id=hod_id)
                db.session.add(faculty)
            elif role == 'HOD':
                dept = request.form.get('hod_department')
                rank = request.form.get('hod_rank') # HOD, Asst_HOD
                hod = HODDetails(user_id=new_user.id, department=dept, rank=rank)
                db.session.add(hod)
            
            db.session.commit()
            flash('User created successfully!', 'success')
            return redirect(url_for('manage_users'))

        faculty_users = User.query.filter_by(role='Faculty').all()
        student_users = User.query.filter_by(role='Student').all()

        # Fetch unique departments and courses for dropdowns
        f_depts = db.session.query(FacultyDetails.department).distinct().all()
        s_depts = db.session.query(StudentDetails.department).distinct().all()
        departments = sorted(list(set([d[0] for d in f_depts if d[0]] + [d[0] for d in s_depts if d[0]])))
        
        courses_query = db.session.query(StudentDetails.course).distinct().all()
        courses = sorted([c[0] for c in courses_query if c[0]])

        return render_template('manage_users.html', faculty=faculty_users, students=student_users, 
                               departments=departments, courses=courses)

    @app.route('/admin/user/edit/<int:id>', methods=['GET', 'POST'])
    @login_required
    @role_required('Admin')
    def edit_user(id):
        from models import User, StudentDetails, FacultyDetails
        user = User.query.get_or_404(id)
        if request.method == 'POST':
            user.username = request.form.get('username')
            if request.form.get('password'):
                user.set_password(request.form.get('password'))
            
            if user.role == 'Student':
                user.student_profile.enrollment_no = request.form.get('enrollment_no')
                user.student_profile.course = request.form.get('course')
                user.student_profile.department = request.form.get('department')
                user.student_profile.semester = request.form.get('semester')
            elif user.role == 'Faculty':
                user.faculty_profile.department = request.form.get('department')
                user.faculty_profile.designation = request.form.get('designation')
            
            db.session.commit()
            flash('User updated successfully!', 'success')
            return redirect(url_for('manage_users'))
            
        # Fetch unique departments and courses for dropdowns
        f_depts = db.session.query(FacultyDetails.department).distinct().all()
        s_depts = db.session.query(StudentDetails.department).distinct().all()
        departments = sorted(list(set([d[0] for d in f_depts if d[0]] + [d[0] for d in s_depts if d[0]])))
        
        courses_query = db.session.query(StudentDetails.course).distinct().all()
        courses = sorted([c[0] for c in courses_query if c[0]])

        return render_template('edit_user.html', user=user, departments=departments, courses=courses)

    @app.route('/admin/user/delete/<int:id>')
    @login_required
    @role_required('Admin')
    def delete_user(id):
        from models import User
        if current_user.id == id:
            flash('You cannot delete yourself!', 'danger')
            return redirect(url_for('manage_users'))
        user = User.query.get_or_404(id)
        db.session.delete(user)
        db.session.commit()
        flash(f'User {user.username} and all associated data deleted!', 'warning')
        return redirect(url_for('manage_users'))

    @app.route('/hod/allot_class', methods=['GET', 'POST'])
    @login_required
    @role_required('HOD')
    def allot_class():
        from models import FacultyDetails, ClassAllotment, StudentDetails
        faculties = FacultyDetails.query.all()
        allotments = ClassAllotment.query.all()
        
        # Unique data for dropdowns
        unique_depts = [x[0] for x in db.session.query(FacultyDetails.department).distinct().all()]
        unique_depts += [x[0] for x in db.session.query(StudentDetails.department).distinct().all()]
        unique_depts = sorted(list(set(filter(None, unique_depts))))
        
        unique_classes = [x[0] for x in db.session.query(StudentDetails.class_name).distinct().all()]
        unique_classes += [x[0] for x in db.session.query(ClassAllotment.class_name).distinct().all()]
        unique_classes = sorted(list(set(filter(None, unique_classes))))
        
        unique_subs = [x[0] for x in db.session.query(ClassAllotment.subject).distinct().all()]
        unique_subs = sorted(list(set(filter(None, unique_subs))))

        if request.method == 'POST':
            faculty_id = request.form.get('faculty_id')
            faculty_name = request.form.get('faculty_name')
            dept = request.form.get('department')
            cls_name = request.form.get('class_name')
            subject = request.form.get('subject')
            
            allotment = ClassAllotment(faculty_id=faculty_id, faculty_name=faculty_name, 
                                     department=dept, class_name=cls_name, subject=subject)
            db.session.add(allotment)
            db.session.commit()
            flash('Faculty successfully assigned to class!', 'success')
            return redirect(url_for('allot_class'))
        return render_template('allot_classes.html', faculties=faculties, allotments=allotments, 
                               departments=unique_depts, classes=unique_classes, subjects=unique_subs)

    @app.route('/hod/allot_class/delete/<int:id>')
    @login_required
    @role_required('HOD')
    def delete_allotment(id):
        from models import ClassAllotment
        allotment = ClassAllotment.query.get_or_404(id)
        db.session.delete(allotment)
        db.session.commit()
        flash('Assignment removed!', 'warning')
        return redirect(url_for('allot_class'))

    return app

import os

if __name__ == '__main__':
    app = create_app()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
