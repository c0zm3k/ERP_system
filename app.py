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

    @app.route('/timetable')
    @login_required
    def view_timetable():
        from models import Timetable
        slots = Timetable.query.all()
        return render_template('timetable.html', slots=slots)

    @app.route('/timetable/add', methods=['GET', 'POST'])
    @login_required
    @role_required('Admin')
    def add_timetable():
        from models import Timetable, ClassAllotment
        # Fetch unique subjects and classes already added
        unique_subs = [x[0] for x in db.session.query(ClassAllotment.subject).distinct().all()]
        unique_subs += [x[0] for x in db.session.query(Timetable.subject).distinct().all()]
        unique_subs = sorted(list(set(filter(None, unique_subs))))
        
        unique_classes = [x[0] for x in db.session.query(ClassAllotment.class_name).distinct().all()]
        unique_classes += [x[0] for x in db.session.query(Timetable.class_name).distinct().all()]
        unique_classes = sorted(list(set(filter(None, unique_classes))))

        if request.method == 'POST':
            day = request.form.get('day')
            start_hour = request.form.get('start_hour')
            start_minute = request.form.get('start_minute')
            start_period = request.form.get('start_period')
            end_hour = request.form.get('end_hour')
            end_minute = request.form.get('end_minute')
            end_period = request.form.get('end_period')
            subject = request.form.get('subject')
            
            print(f"DEBUG POST: day={day}, subject={subject}, start_hour={start_hour}, start_minute={start_minute}, start_period={start_period}")
            
            time_slot = f"{start_hour}:{start_minute} {start_period} - {end_hour}:{end_minute} {end_period}"
            
            # Auto-assign faculty if an allotment exists (by subject only now)
            allotment = ClassAllotment.query.filter_by(subject=subject).first()
            faculty_id = allotment.faculty_id if allotment else None
            class_name = allotment.class_name if allotment else 'General'
            
            print(f"DEBUG SAVING: time_slot='{time_slot}', faculty_id={faculty_id}, class_name={class_name}")
            
            if not day or not subject or not time_slot:
                flash('Error: Missing required fields', 'danger')
                return redirect(url_for('add_timetable'))

            new_slot = Timetable(day=day, time_slot=time_slot, subject=subject, class_name=class_name, faculty_id=faculty_id)
            db.session.add(new_slot)
            db.session.commit()
            flash('Timetable slort added (Faculty auto-assigned)!', 'success')
            return redirect(url_for('view_timetable'))
        return render_template('add_timetable.html', subjects=unique_subs, classes=unique_classes)

    @app.route('/timetable/edit/<int:id>', methods=['GET', 'POST'])
    @login_required
    @role_required('Admin')
    def edit_timetable(id):
        from models import Timetable, ClassAllotment
        slot = Timetable.query.get_or_404(id)
        
        # Unique data for dropdowns
        unique_subs = [x[0] for x in db.session.query(ClassAllotment.subject).distinct().all()]
        unique_subs += [x[0] for x in db.session.query(Timetable.subject).distinct().all()]
        unique_subs = sorted(list(set(filter(None, unique_subs))))
        
        unique_classes = [x[0] for x in db.session.query(ClassAllotment.class_name).distinct().all()]
        unique_classes += [x[0] for x in db.session.query(Timetable.class_name).distinct().all()]
        unique_classes = sorted(list(set(filter(None, unique_classes))))

        if request.method == 'POST':
            slot.day = request.form.get('day')
            start_hour = request.form.get('start_hour')
            start_minute = request.form.get('start_minute')
            start_period = request.form.get('start_period')
            end_hour = request.form.get('end_hour')
            end_minute = request.form.get('end_minute')
            end_period = request.form.get('end_period')
            
            slot.time_slot = f"{start_hour}:{start_minute} {start_period} - {end_hour}:{end_minute} {end_period}"
            slot.subject = request.form.get('subject')
            
            # Auto-assign faculty if an allotment exists (by subject only)
            allotment = ClassAllotment.query.filter_by(subject=slot.subject).first()
            slot.faculty_id = allotment.faculty_id if allotment else None
            slot.class_name = allotment.class_name if allotment else 'General'
            
            db.session.commit()
            flash('Timetable slort updated (Faculty auto-assigned)!', 'success')
            return redirect(url_for('view_timetable'))
            
        # Parse existing time_slot for pre-filling
        try:
            # HH:MM AM - HH:MM PM
            start, end = slot.time_slot.split(' - ')
            start_time, start_period = start.split(' ')
            start_h, start_m = start_time.split(':')
            end_time, end_period = end.split(' ')
            end_h, end_m = end_time.split(':')
            times = {
                'sh': start_h, 'sm': start_m, 'sp': start_period,
                'eh': end_h, 'em': end_m, 'ep': end_period
            }
        except:
            times = {'sh': '09', 'sm': '00', 'sp': 'AM', 'eh': '10', 'em': '00', 'ep': 'AM'}

        return render_template('edit_timetable.html', slot=slot, 
                               subjects=unique_subs, classes=unique_classes, times=times)

    @app.route('/timetable/delete/<int:id>')
    @login_required
    @role_required('Admin')
    def delete_timetable(id):
        from models import Timetable
        slot = Timetable.query.get_or_404(id)
        db.session.delete(slot)
        db.session.commit()
        flash('Timetable slot deleted!', 'warning')
        return redirect(url_for('view_timetable'))

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

    @app.route('/admin')
    @login_required
    @role_required('Admin')
    def admin_panel():
        from models import User, StudentDetails, FacultyDetails
        stats = {
            'total_users': User.query.count(),
            'total_students': StudentDetails.query.count(),
            'total_faculty': FacultyDetails.query.count()
        }
        return render_template('admin_panel.html', stats=stats)

    @app.route('/admin/users', methods=['GET', 'POST'])
    @login_required
    @role_required('Admin')
    def manage_users():
        from models import User, StudentDetails, FacultyDetails
        if request.method == 'POST':
            username = request.form.get('username')
            password = request.form.get('password')
            role = request.form.get('role')
            
            if User.query.filter_by(username=username).first():
                flash('Username already exists', 'danger')
                return redirect(url_for('manage_users'))
                
            new_user = User(username=username, role=role)
            new_user.set_password(password)
            db.session.add(new_user)
            db.session.flush()
            
            if role == 'Student':
                enrollment = request.form.get('enrollment_no')
                course = request.form.get('course')
                dept = request.form.get('student_department')
                semester = request.form.get('semester')
                # Removed class_name as per user request
                student = StudentDetails(user_id=new_user.id, enrollment_no=enrollment, 
                                        course=course, department=dept, semester=semester)
                db.session.add(student)
            elif role == 'Faculty':
                dept = request.form.get('faculty_department')
                desig = request.form.get('designation')
                faculty = FacultyDetails(user_id=new_user.id, department=dept, designation=desig)
                db.session.add(faculty)
            
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

    @app.route('/admin/allot_class', methods=['GET', 'POST'])
    @login_required
    @role_required('Admin')
    def allot_class():
        from models import FacultyDetails, ClassAllotment, StudentDetails, Timetable
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
        unique_subs += [x[0] for x in db.session.query(Timetable.subject).distinct().all()]
        unique_subs = sorted(list(set(filter(None, unique_subs))))

        if request.method == 'POST':
            faculty_id = request.form.get('faculty_id')
            dept = request.form.get('department')
            cls_name = request.form.get('class_name')
            subject = request.form.get('subject')
            
            allotment = ClassAllotment(faculty_id=faculty_id, department=dept, class_name=cls_name, subject=subject)
            db.session.add(allotment)
            db.session.commit()
            flash('Class allotted to faculty!', 'success')
            return redirect(url_for('allot_class'))
        return render_template('allot_classes.html', faculties=faculties, allotments=allotments, 
                               departments=unique_depts, classes=unique_classes, subjects=unique_subs)

    @app.route('/admin/allot_class/delete/<int:id>')
    @login_required
    @role_required('Admin')
    def delete_allotment(id):
        from models import ClassAllotment
        allotment = ClassAllotment.query.get_or_404(id)
        db.session.delete(allotment)
        db.session.commit()
        flash('Allotment removed!', 'warning')
        return redirect(url_for('allot_class'))

    return app

import os

if __name__ == '__main__':
    app = create_app()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
