"""Main app routes: dashboard, attendance, leaves, fees, certificates, notes, calendar."""
import os
from datetime import datetime

from flask import Blueprint, render_template, redirect, url_for, flash, request, send_from_directory, current_app, jsonify
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from extensions import db
from utils import role_required

main_bp = Blueprint('main', __name__)


@main_bp.route('/dashboard')
@login_required
def dashboard():
    allotments = []
    student_classes = []
    if current_user.role == 'Faculty':
        allotments = current_user.faculty_profile.allotments.all()
    elif current_user.role == 'Student' and current_user.student_profile:
        from models import ClassAllotment
        sp = current_user.student_profile
        q = ClassAllotment.query.filter_by(
            department=sp.department,
            class_name=sp.class_name
        )
        if getattr(sp, 'course', None):
            q = q.filter(ClassAllotment.course == sp.course)
        if getattr(sp, 'semester', None) is not None:
            q = q.filter(ClassAllotment.semester == sp.semester)
        student_classes = q.all()
    return render_template('dashboard.html', allotments=allotments, student_classes=student_classes)


@main_bp.route('/attendance', methods=['GET', 'POST'])
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
            q = StudentDetails.query.filter_by(
                department=selected_allotment.department,
                class_name=selected_allotment.class_name
            )
            if getattr(selected_allotment, 'course', None):
                q = q.filter_by(course=selected_allotment.course)
            if getattr(selected_allotment, 'semester', None) is not None:
                q = q.filter_by(semester=selected_allotment.semester)
            students = q.all()

            existing_attendance = Attendance.query.filter_by(
                date=date_obj,
                subject=selected_allotment.subject
            ).filter(Attendance.student_id.in_([s.id for s in students])).all()

            marked_status = {a.student_id: a.status for a in existing_attendance}

    present_count = list(marked_status.values()).count('Present')
    absent_count = list(marked_status.values()).count('Absent')

    if request.method == 'POST':
        allotment_id = request.form.get('allotment_id', type=int)
        allotment = ClassAllotment.query.get(allotment_id)
        if not allotment or allotment.faculty_id != faculty.id:
            flash('Invalid allotment.', 'danger')
            return redirect(url_for('main.mark_attendance'))

        post_date_str = request.form.get('date')
        post_date_obj = datetime.strptime(post_date_str, '%Y-%m-%d').date() if post_date_str else datetime.utcnow().date()
        subject = allotment.subject

        q = StudentDetails.query.filter_by(
            department=allotment.department,
            class_name=allotment.class_name
        )
        if getattr(allotment, 'course', None):
            q = q.filter_by(course=allotment.course)
        if getattr(allotment, 'semester', None) is not None:
            q = q.filter_by(semester=allotment.semester)
        students_to_mark = q.all()

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
        return redirect(url_for('main.dashboard'))

    return render_template('attendance.html', students=students, today=date_str,
                          allotments=allotments, selected_allotment=selected_allotment,
                          marked_status=marked_status, present_count=present_count, absent_count=absent_count)


@main_bp.route('/my_attendance')
@login_required
@role_required('Student')
def view_attendance():
    from models import Attendance
    attendances = Attendance.query.filter_by(student_id=current_user.student_profile.id).all()
    present_count = sum(1 for a in attendances if a.status == 'Present')
    absent_count = sum(1 for a in attendances if a.status == 'Absent')
    return render_template('view_attendance.html', attendances=attendances, present=present_count, absent=absent_count)


@main_bp.route('/attendance/analysis')
@login_required
@role_required('Student')
def attendance_analysis():
    from models import Attendance
    from datetime import timedelta, date
    
    student_id = current_user.student_profile.id
    all_attendances = Attendance.query.filter_by(student_id=student_id).order_by(Attendance.date.desc()).all()
    
    # Get analysis period from request
    period = request.args.get('period', 'semester')  # semester, month, week, day
    
    # Calculate date range based on period
    today = date.today()
    
    if period == 'day':
        filter_date = today
        period_label = f"Today ({today})"
        date_filter = all_attendances
    elif period == 'week':
        start_date = today - timedelta(days=today.weekday())
        period_label = f"This Week ({start_date} to {today})"
        date_filter = [a for a in all_attendances if start_date <= a.date <= today]
    elif period == 'month':
        start_date = date(today.year, today.month, 1)
        period_label = f"This Month ({start_date.strftime('%B %Y')})"
        date_filter = [a for a in all_attendances if a.date.year == today.year and a.date.month == today.month]
    else:  # semester
        # Assuming semester is 6 months
        start_date = date(today.year, (today.month - 1) // 6 * 6 + 1, 1)
        semester_num = (today.month - 1) // 6 + 1
        period_label = f"Semester {semester_num} (6 months)"
        date_filter = [a for a in all_attendances if a.date >= start_date]
    
    # Calculate statistics
    present_count = sum(1 for a in date_filter if a.status == 'Present')
    absent_count = sum(1 for a in date_filter if a.status == 'Absent')
    total_classes = len(date_filter)
    
    if total_classes > 0:
        attendance_percentage = round((present_count / total_classes) * 100, 1)
    else:
        attendance_percentage = 0
    
    # Group by subject
    subject_stats = {}
    for attendance in date_filter:
        subject = attendance.subject or 'Unassigned'
        if subject not in subject_stats:
            subject_stats[subject] = {'present': 0, 'absent': 0, 'total': 0}
        subject_stats[subject]['total'] += 1
        if attendance.status == 'Present':
            subject_stats[subject]['present'] += 1
        else:
            subject_stats[subject]['absent'] += 1
    
    # Calculate per-subject percentages
    for subject in subject_stats:
        if subject_stats[subject]['total'] > 0:
            subject_stats[subject]['percentage'] = round(
                (subject_stats[subject]['present'] / subject_stats[subject]['total']) * 100, 1
            )
    
    # Group by date for daily breakdown
    daily_breakdown = {}
    for attendance in date_filter:
        date_str = attendance.date.strftime('%Y-%m-%d')
        if date_str not in daily_breakdown:
            daily_breakdown[date_str] = {'present': 0, 'absent': 0, 'classes': []}
        if attendance.status == 'Present':
            daily_breakdown[date_str]['present'] += 1
        else:
            daily_breakdown[date_str]['absent'] += 1
        daily_breakdown[date_str]['classes'].append({
            'subject': attendance.subject or 'Unassigned',
            'status': attendance.status
        })
    
    # Sort daily breakdown by date (most recent first)
    daily_breakdown = dict(sorted(daily_breakdown.items(), reverse=True))
    
    return render_template('attendance_analysis.html',
                         period=period,
                         period_label=period_label,
                         present_count=present_count,
                         absent_count=absent_count,
                         total_classes=total_classes,
                         attendance_percentage=attendance_percentage,
                         subject_stats=subject_stats,
                         daily_breakdown=daily_breakdown,
                         detailed_attendances=date_filter)


@main_bp.route('/leaves', methods=['GET', 'POST'])
@login_required
def leaves():
    from models import Leaves
    if request.method == 'POST':
        leave_type = request.form.get('type')
        reason = request.form.get('reason')
        start_date = datetime.strptime(request.form.get('start_date'), '%Y-%m-%d').date()
        end_date = datetime.strptime(request.form.get('end_date'), '%Y-%m-%d').date()

        if current_user.role == 'Student':
            initial_status = 'Pending_Faculty'
        elif current_user.role == 'Faculty':
            initial_status = 'Pending_HOD'
        elif current_user.role == 'HOD':
            initial_status = 'Pending_Admin'
        else:
            initial_status = 'Approved'

        new_leave = Leaves(user_id=current_user.id, type=leave_type, reason=reason,
                            start_date=start_date, end_date=end_date, status=initial_status)
        db.session.add(new_leave)
        db.session.commit()
        flash('Leave request submitted and routed for approval!', 'success')
        return redirect(url_for('main.leaves'))

    leaves_left = current_user.total_leaves - current_user.leaves_taken

    if current_user.role == 'Admin':
        all_leaves = Leaves.query.filter(Leaves.status.in_(['Pending_Admin', 'Approved', 'Rejected'])).all()
    elif current_user.role == 'HOD':
        all_leaves = Leaves.query.filter(Leaves.status.in_(['Pending_HOD', 'Pending_Admin'])).all()
    elif current_user.role == 'Faculty':
        all_leaves = Leaves.query.filter(Leaves.status.in_(['Pending_Faculty', 'Pending_HOD'])).all()
    else:
        all_leaves = current_user.leaves.all()

    return render_template('leaves.html', leaves=all_leaves, left=leaves_left)


@main_bp.route('/leaves/approve/<int:id>')
@login_required
def approve_leave(id):
    from models import Leaves
    leave = Leaves.query.get_or_404(id)
    requester = leave.user

    if current_user.role == 'Faculty' and leave.status == 'Pending_Faculty':
        leave.status = 'Pending_HOD'
        flash('Level 1 approval complete! Routed to HOD.', 'success')
    elif current_user.role == 'HOD' and leave.status == 'Pending_HOD':
        if requester.role == 'Student':
            leave.status = 'Approved'
            requester.leaves_taken += (leave.end_date - leave.start_date).days + 1
        else:
            leave.status = 'Pending_Admin'
        flash('Departmental approval complete!', 'success')
    elif (current_user.role == 'Admin' or (current_user.role == 'HOD' and current_user.hod_profile.rank == 'Asst_HOD')) and leave.status == 'Pending_Admin':
        leave.status = 'Approved'
        requester.leaves_taken += (leave.end_date - leave.start_date).days + 1
        flash('Leave fully authorized!', 'success')
    else:
        flash('Unauthorized or invalid flow.', 'danger')

    db.session.commit()
    return redirect(url_for('main.leaves'))


@main_bp.route('/leaves/reject/<int:id>')
@login_required
def reject_leave(id):
    from models import Leaves
    leave = Leaves.query.get_or_404(id)
    leave.status = 'Rejected'
    db.session.commit()
    flash('Leave request denied.', 'warning')
    return redirect(url_for('main.leaves'))


@main_bp.route('/fees')
@login_required
def view_fees():
    from models import Fee
    if current_user.role == 'Student':
        fees = current_user.student_profile.fees.all()
    elif current_user.role == 'Admin':
        fees = Fee.query.all()
    else:
        fees = []
    return render_template('fees.html', fees=fees)


@main_bp.route('/certificates')
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


@main_bp.route('/notes', methods=['GET', 'POST'])
@login_required
def notes():
    upload_folder = current_app.config['UPLOAD_FOLDER']
    files = os.listdir(upload_folder)
    notes_list = [f for f in files if os.path.isfile(os.path.join(upload_folder, f))]

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
            file.save(os.path.join(upload_folder, filename))
            flash('File uploaded successfully!', 'success')
            return redirect(url_for('main.notes'))

    return render_template('notes.html', notes=notes_list)


@main_bp.route('/download/<path:filename>')
@login_required
def download_file(filename):
    return send_from_directory(current_app.config['UPLOAD_FOLDER'], filename, as_attachment=True)


@main_bp.route('/calendar')
@login_required
def calendar():
    from models import Event
    all_events = Event.query.order_by(Event.event_date.asc()).all()
    return render_template('calendar.html', events=all_events)

@main_bp.route('/broadcasts')
@login_required
def broadcasts():
    from models import Broadcast
    
    # Get institution-wide broadcasts
    institution_broadcasts = Broadcast.query.filter_by(scope='institution').order_by(Broadcast.is_pinned.desc(), Broadcast.created_at.desc()).all()
    
    # Get department-specific broadcasts if user belongs to a department
    dept_broadcasts = []
    if current_user.department:
        dept_broadcasts = Broadcast.query.filter_by(scope='department', department=current_user.department).order_by(Broadcast.is_pinned.desc(), Broadcast.created_at.desc()).all()
    
    return render_template('broadcasts.html', 
                         institution_broadcasts=institution_broadcasts,
                         dept_broadcasts=dept_broadcasts)


@main_bp.route('/api/broadcasts/refresh')
@login_required
def refresh_broadcasts():
    """API endpoint for auto-refreshing broadcasts (60-second interval)."""
    from models import Broadcast
    
    # Get institution-wide broadcasts
    institution_broadcasts = Broadcast.query.filter_by(scope='institution').order_by(Broadcast.is_pinned.desc(), Broadcast.created_at.desc()).all()
    
    # Get department-specific broadcasts if user belongs to a department
    dept_broadcasts = []
    if current_user.department:
        dept_broadcasts = Broadcast.query.filter_by(scope='department', department=current_user.department).order_by(Broadcast.is_pinned.desc(), Broadcast.created_at.desc()).all()
    
    def serialize_broadcast(b):
        return {
            'id': b.id,
            'title': b.title,
            'content': b.content,
            'created_by': b.created_by.username,
            'created_at': b.created_at.strftime('%b %d, %Y at %I:%M %p'),
            'is_pinned': b.is_pinned,
            'scope': b.scope,
            'department': b.department or ''
        }
    
    return jsonify({
        'institution_broadcasts': [serialize_broadcast(b) for b in institution_broadcasts],
        'dept_broadcasts': [serialize_broadcast(b) for b in dept_broadcasts],
        'timestamp': datetime.utcnow().isoformat()
    })