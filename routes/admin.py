"""Admin routes: panel, user management, fees, certificates, events."""
import os
from datetime import datetime

from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from extensions import db
from utils import role_required

admin_bp = Blueprint('admin', __name__)


@admin_bp.route('/admin')
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
    all_faculty = FacultyDetails.query.join(User).order_by(User.department.asc()).all()
    all_hods = HODDetails.query.join(User).order_by(User.department.asc(), HODDetails.rank.asc()).all()
    return render_template('admin_panel.html', stats=stats, faculty=all_faculty, hods=all_hods)


@admin_bp.route('/admin/users', methods=['GET', 'POST'])
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
            return redirect(url_for('admin.manage_users'))

        if User.query.filter_by(username=username).first():
            flash('Username already exists', 'danger')
            return redirect(url_for('admin.manage_users'))

        new_user = User(username=username, role=role)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.flush()

        if role == 'Faculty':
            dept = request.form.get('faculty_department', '').strip()
            desig = request.form.get('designation', '')
            if not dept:
                flash('Please select a department for the faculty.', 'danger')
                return redirect(url_for('admin.manage_users'))
            hod_id = request.form.get('faculty_hod_id', type=int)
            if hod_id:
                hod_row = HODDetails.query.get(hod_id)
                if not hod_row or hod_row.department != dept:
                    hod_id = None
            if not hod_id:
                hod_row = HODDetails.query.filter_by(department=dept, rank='HOD').first() or HODDetails.query.filter_by(department=dept).first()
                hod_id = hod_row.id if hod_row else None
            new_user.department = dept
            faculty = FacultyDetails(user_id=new_user.id, department=dept, designation=desig, hod_id=hod_id)
            db.session.add(faculty)
        elif role == 'HOD':
            dept = request.form.get('hod_department')
            rank = request.form.get('hod_rank')
            hod = HODDetails(user_id=new_user.id, department=dept, rank=rank)
            db.session.add(hod)

        db.session.commit()
        flash('User created successfully!', 'success')
        return redirect(url_for('admin.manage_users'))

    filter_role = request.args.get('filter_role', '')
    filter_department = request.args.get('filter_department', '')

    faculty_details = FacultyDetails.query.all()
    student_users = User.query.filter_by(role='Student').all()
    admin_users = User.query.filter_by(role='Admin').all()
    hods = HODDetails.query.all()
    hods_sorted = sorted(hods, key=lambda h: (h.department or '', h.rank or ''))

    if filter_role or filter_department:
        if filter_role == 'Admin':
            hods_sorted, faculty_details, student_users = [], [], []
        elif filter_role == 'HOD':
            admin_users = []
            hods_sorted = [h for h in hods_sorted if not filter_department or h.department == filter_department]
            faculty_details, student_users = [], []
        elif filter_role == 'Faculty':
            admin_users, hods_sorted = [], []
            faculty_details = [f for f in faculty_details if not filter_department or f.department == filter_department]
            student_users = []
        elif filter_role == 'Student':
            admin_users, hods_sorted, faculty_details = [], [], []
            student_users = [s for s in student_users if s.student_profile and (not filter_department or s.student_profile.department == filter_department)]
        else:
            if filter_department:
                admin_users = []
                hods_sorted = [h for h in hods_sorted if h.department == filter_department]
                faculty_details = [f for f in faculty_details if f.department == filter_department]
                student_users = [s for s in student_users if s.student_profile and s.student_profile.department == filter_department]

    dept_rows = db.session.query(HODDetails.department).distinct().all()
    f_dept_rows = db.session.query(FacultyDetails.department).distinct().all()
    s_dept_rows = db.session.query(StudentDetails.department).distinct().all()
    all_dept_set = set(d[0] for d in dept_rows if d[0]) | set(d[0] for d in f_dept_rows if d[0]) | set(d[0] for d in s_dept_rows if d[0])
    departments = sorted(list(set(d[0] for d in dept_rows if d[0])))
    all_departments = sorted(list(all_dept_set))
    courses_query = db.session.query(StudentDetails.course).distinct().all()
    courses = sorted([c[0] for c in courses_query if c[0]])

    return render_template('manage_users.html', faculty=faculty_details, students=student_users,
                          admins=admin_users, hods=hods_sorted, departments=departments, courses=courses,
                          filter_role=filter_role, filter_department=filter_department, all_departments=all_departments)


@admin_bp.route('/admin/user/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@role_required('Admin')
def edit_user(id):
    from models import User, StudentDetails, FacultyDetails, HODDetails
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
        return redirect(url_for('admin.manage_users'))

    f_depts = db.session.query(FacultyDetails.department).distinct().all()
    s_depts = db.session.query(StudentDetails.department).distinct().all()
    hod_depts = db.session.query(HODDetails.department).distinct().all()
    departments = sorted(list(set([d[0] for d in f_depts if d[0]] + [d[0] for d in s_depts if d[0]] + [d[0] for d in hod_depts if d[0]])))
    courses_query = db.session.query(StudentDetails.course).distinct().all()
    courses = sorted([c[0] for c in courses_query if c[0]])
    return render_template('edit_user.html', user=user, departments=departments, courses=courses)


@admin_bp.route('/admin/user/delete/<int:id>')
@login_required
@role_required('Admin')
def delete_user(id):
    from models import User
    if current_user.id == id:
        flash('You cannot delete yourself!', 'danger')
        return redirect(url_for('admin.manage_users'))
    user = User.query.get_or_404(id)
    db.session.delete(user)
    db.session.commit()
    flash(f'User {user.username} and all associated data deleted!', 'warning')
    return redirect(url_for('admin.manage_users'))


@admin_bp.route('/admin/fees/add', methods=['POST'])
@login_required
@role_required('Admin')
def add_fee():
    from models import Fee
    student_id = request.form.get('student_id')
    title = request.form.get('title')
    amount = request.form.get('amount')
    due_date = datetime.strptime(request.form.get('due_date'), '%Y-%m-%d').date()
    semester = request.form.get('semester')
    new_fee = Fee(student_id=student_id, title=title, amount=amount, due_date=due_date, semester=semester)
    db.session.add(new_fee)
    db.session.commit()
    flash('Fee record created!', 'success')
    return redirect(url_for('main.view_fees'))


@admin_bp.route('/admin/certificates/upload', methods=['POST'])
@login_required
@role_required('Admin')
def upload_certificate():
    from models import Certificate
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
        upload_folder = current_app.config['UPLOAD_FOLDER']
        filename = secure_filename(file.filename)
        upload_path = os.path.join(upload_folder, 'certificates', filename)
        if not os.path.exists(os.path.dirname(upload_path)):
            os.makedirs(os.path.dirname(upload_path))
        file.save(upload_path)
        new_cert = Certificate(student_id=student_id, title=title, category=category, file_path=filename)
        db.session.add(new_cert)
        db.session.commit()
        flash('Certificate uploaded!', 'success')

    return redirect(url_for('main.view_certificates'))


@admin_bp.route('/admin/events/add', methods=['POST'])
@login_required
@role_required('Admin')
def add_event():
    from models import Event
    title = request.form.get('title')
    description = request.form.get('description')
    event_date_str = request.form.get('event_date')

    if not title or not event_date_str:
        flash('Error: Missing required fields', 'danger')
        return redirect(url_for('main.calendar'))

    event_date = datetime.strptime(event_date_str, '%Y-%m-%d').date()
    new_event = Event(title=title, description=description, event_date=event_date)
    db.session.add(new_event)
    db.session.commit()
    flash('Event added!', 'success')
    return redirect(url_for('main.calendar'))

@admin_bp.route('/admin/broadcasts', methods=['GET', 'POST'])
@login_required
@role_required('Admin')
def manage_broadcasts():
    from models import Broadcast
    if request.method == 'POST':
        title = request.form.get('title')
        content = request.form.get('content')
        
        if not title or not content:
            flash('Title and content are required', 'danger')
            return redirect(url_for('admin.manage_broadcasts'))
        
        new_broadcast = Broadcast(
            title=title,
            content=content,
            created_by_id=current_user.id,
            scope='institution'
        )
        db.session.add(new_broadcast)
        db.session.commit()
        flash('Institution-wide broadcast created successfully!', 'success')
        return redirect(url_for('admin.manage_broadcasts'))
    
    broadcasts = Broadcast.query.filter_by(scope='institution').order_by(Broadcast.created_at.desc()).all()
    return render_template('admin_broadcasts.html', broadcasts=broadcasts)


@admin_bp.route('/admin/broadcasts/<int:id>/delete', methods=['POST'])
@login_required
@role_required('Admin')
def delete_broadcast(id):
    from models import Broadcast
    broadcast = Broadcast.query.get_or_404(id)
    if broadcast.scope != 'institution':
        flash('Unauthorized', 'danger')
        return redirect(url_for('admin.manage_broadcasts'))
    
    db.session.delete(broadcast)
    db.session.commit()
    flash('Broadcast deleted', 'success')
    return redirect(url_for('admin.manage_broadcasts'))


@admin_bp.route('/admin/broadcasts/<int:id>/pin', methods=['POST'])
@login_required
@role_required('Admin')
def pin_broadcast(id):
    from models import Broadcast
    broadcast = Broadcast.query.get_or_404(id)
    if broadcast.scope != 'institution':
        flash('Unauthorized', 'danger')
        return redirect(url_for('admin.manage_broadcasts'))
    
    broadcast.is_pinned = not broadcast.is_pinned
    db.session.commit()
    flash(f'Broadcast {"pinned" if broadcast.is_pinned else "unpinned"}', 'success')
    return redirect(url_for('admin.manage_broadcasts'))