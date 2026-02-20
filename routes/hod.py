"""HOD routes: panel, class allotment."""
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user

from extensions import db
from utils import role_required

hod_bp = Blueprint('hod', __name__)


@hod_bp.route('/hod', methods=['GET', 'POST'])
@login_required
@role_required('HOD')
def hod_panel():
    from models import User, StudentDetails, FacultyDetails, Leaves, HODDetails
    hod = current_user.hod_profile

    if request.method == 'POST' and 'enrollment_no' in request.form:
        username = request.form.get('username')
        password = request.form.get('password')
        enrollment = request.form.get('enrollment_no')
        course = request.form.get('course')
        semester = request.form.get('semester')

        if User.query.filter_by(username=username).first():
            flash('Username already exists', 'danger')
            return redirect(url_for('hod.hod_panel'))

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
        return redirect(url_for('hod.hod_panel'))

    stats = {
        'total_students': hod.students.count(),
        'total_faculty': hod.faculties.count(),
        'pending_leaves': Leaves.query.filter_by(status='Pending_HOD').count(),
    }
    dept_faculty = hod.faculties.all()
    dept_students = hod.students.all()
    return render_template('hod_panel.html', stats=stats, faculty=dept_faculty, students=dept_students)


@hod_bp.route('/hod/slots', methods=['GET', 'POST'])
@login_required
@role_required('HOD')
def time_slots():
    from models import TimeSlot
    hod = current_user.hod_profile
    slots = TimeSlot.query.filter_by(hod_id=hod.id).order_by(TimeSlot.day_of_week, TimeSlot.start_time).all()
    if request.method == 'POST':
        name = request.form.get('slot_name', '').strip()
        day = request.form.get('day_of_week')
        start_time = request.form.get('start_time')
        end_time = request.form.get('end_time')
        if name and day and start_time and end_time:
            slot = TimeSlot(hod_id=hod.id, name=name, day_of_week=day, start_time=start_time,
                            end_time=end_time, department=hod.department)
            db.session.add(slot)
            db.session.commit()
            flash('Time slot created.', 'success')
            return redirect(url_for('hod.time_slots'))
        flash('Please fill all slot fields.', 'danger')
    return render_template('time_slots.html', slots=slots)


@hod_bp.route('/hod/slots/delete/<int:id>')
@login_required
@role_required('HOD')
def delete_slot(id):
    from models import TimeSlot
    slot = TimeSlot.query.get_or_404(id)
    if slot.hod_id != current_user.hod_profile.id:
        flash('Not allowed.', 'danger')
        return redirect(url_for('hod.time_slots'))
    db.session.delete(slot)
    db.session.commit()
    flash('Time slot removed.', 'warning')
    return redirect(url_for('hod.time_slots'))


@hod_bp.route('/hod/allot_class', methods=['GET', 'POST'])
@login_required
@role_required('HOD')
def allot_class():
    from models import FacultyDetails, ClassAllotment, StudentDetails, TimeSlot, ClassAllotmentRequest
    hod = current_user.hod_profile
    faculties = FacultyDetails.query.all()
    try:
        allotments = ClassAllotment.query.all()
    except Exception:
        db.session.rollback()
        allotments = []
    try:
        slots = TimeSlot.query.filter_by(hod_id=hod.id).order_by(TimeSlot.day_of_week, TimeSlot.start_time).all()
    except Exception:
        db.session.rollback()
        slots = []
    try:
        incoming_requests = ClassAllotmentRequest.query.filter_by(responding_hod_id=hod.id, status='Pending').all()
    except Exception:
        db.session.rollback()
        incoming_requests = []

    unique_depts = [x[0] for x in db.session.query(FacultyDetails.department).distinct().all()]
    unique_depts += [x[0] for x in db.session.query(StudentDetails.department).distinct().all()]
    unique_depts = sorted(list(set(filter(None, unique_depts))))

    unique_classes = [x[0] for x in db.session.query(StudentDetails.class_name).distinct().all()]
    unique_classes += [x[0] for x in db.session.query(ClassAllotment.class_name).distinct().all()]
    unique_classes = sorted(list(set(filter(None, unique_classes))))

    unique_courses = [x[0] for x in db.session.query(StudentDetails.course).distinct().all()]
    try:
        unique_courses += [x[0] for x in db.session.query(ClassAllotment.course).distinct().all() if x[0]]
    except Exception:
        pass
    unique_courses = sorted(list(set(filter(None, unique_courses))))

    unique_semesters = [x[0] for x in db.session.query(StudentDetails.semester).distinct().all()]
    try:
        unique_semesters += [x[0] for x in db.session.query(ClassAllotment.semester).distinct().all() if x[0] is not None]
    except Exception:
        pass
    unique_semesters = sorted(list(set(x for x in unique_semesters if x is not None)))

    unique_subs = [x[0] for x in db.session.query(ClassAllotment.subject).distinct().all()]
    unique_subs = sorted(list(set(filter(None, unique_subs))))

    if request.method == 'POST':
        faculty_id = request.form.get('faculty_id', type=int)
        faculty_name = request.form.get('faculty_name')
        dept = request.form.get('department')
        cls_name = request.form.get('class_name')
        subject = request.form.get('subject')
        slot_id = request.form.get('slot_id', type=int) or None
        course = request.form.get('course', '').strip() or None
        semester = request.form.get('semester', type=int) if request.form.get('semester') else None
        faculty = FacultyDetails.query.get(faculty_id) if faculty_id else None
        if not faculty:
            flash('Invalid faculty.', 'danger')
            return redirect(url_for('hod.allot_class'))

        if faculty.department != hod.department:
            other_hod_id = faculty.hod_id
            if not other_hod_id:
                flash('That faculty has no HOD; cannot send cross-department request.', 'danger')
                return redirect(url_for('hod.allot_class'))
            req = ClassAllotmentRequest(requesting_hod_id=hod.id, faculty_id=faculty_id, department=dept,
                                        course=course, semester=semester, class_name=cls_name, subject=subject,
                                        slot_id=slot_id, status='Pending', responding_hod_id=other_hod_id)
            db.session.add(req)
            db.session.commit()
            flash('Request sent to the faculty\'s department HOD for approval.', 'success')
        else:
            allotment = ClassAllotment(faculty_id=faculty_id, faculty_name=faculty_name,
                                       department=dept, course=course, semester=semester,
                                       class_name=cls_name, subject=subject, slot_id=slot_id)
            db.session.add(allotment)
            db.session.commit()
            flash('Faculty successfully assigned to class!', 'success')
        return redirect(url_for('hod.allot_class'))

    return render_template('allot_classes.html', faculties=faculties, allotments=allotments,
                          departments=unique_depts, classes=unique_classes, subjects=unique_subs,
                          courses=unique_courses, semesters=unique_semesters,
                          slots=slots, incoming_requests=incoming_requests)


@hod_bp.route('/hod/allot_class/delete/<int:id>')
@login_required
@role_required('HOD')
def delete_allotment(id):
    from models import ClassAllotment
    allotment = ClassAllotment.query.get_or_404(id)
    db.session.delete(allotment)
    db.session.commit()
    flash('Assignment removed!', 'warning')
    return redirect(url_for('hod.allot_class'))


@hod_bp.route('/hod/requests/approve/<int:id>')
@login_required
@role_required('HOD')
def approve_allotment_request(id):
    from models import ClassAllotmentRequest, ClassAllotment
    req = ClassAllotmentRequest.query.get_or_404(id)
    if req.responding_hod_id != current_user.hod_profile.id or req.status != 'Pending':
        flash('Invalid or already processed request.', 'danger')
        return redirect(url_for('hod.allot_class'))
    allotment = ClassAllotment(faculty_id=req.faculty_id, faculty_name=req.faculty.user.username,
                               department=req.department, course=getattr(req, 'course', None),
                               semester=getattr(req, 'semester', None), class_name=req.class_name,
                               subject=req.subject, slot_id=req.slot_id)
    db.session.add(allotment)
    req.status = 'Approved'
    req.responding_hod_id = current_user.hod_profile.id
    db.session.commit()
    flash('Request approved; faculty assigned to class.', 'success')
    return redirect(url_for('hod.allot_class'))


@hod_bp.route('/hod/requests/reject/<int:id>')
@login_required
@role_required('HOD')
def reject_allotment_request(id):
    from models import ClassAllotmentRequest
    req = ClassAllotmentRequest.query.get_or_404(id)
    if req.responding_hod_id != current_user.hod_profile.id or req.status != 'Pending':
        flash('Invalid or already processed request.', 'danger')
        return redirect(url_for('hod.allot_class'))
    req.status = 'Rejected'
    db.session.commit()
    flash('Request rejected.', 'warning')
    return redirect(url_for('hod.allot_class'))

@hod_bp.route('/hod/broadcasts', methods=['GET', 'POST'])
@login_required
@role_required('HOD')
def manage_dept_broadcasts():
    from models import Broadcast
    hod = current_user.hod_profile
    
    if request.method == 'POST':
        title = request.form.get('title')
        content = request.form.get('content')
        
        if not title or not content:
            flash('Title and content are required', 'danger')
            return redirect(url_for('hod.manage_dept_broadcasts'))
        
        new_broadcast = Broadcast(
            title=title,
            content=content,
            created_by_id=current_user.id,
            scope='department',
            department=hod.department
        )
        db.session.add(new_broadcast)
        db.session.commit()
        flash('Department broadcast created successfully!', 'success')
        return redirect(url_for('hod.manage_dept_broadcasts'))
    
    broadcasts = Broadcast.query.filter_by(scope='department', department=hod.department).order_by(Broadcast.created_at.desc()).all()
    return render_template('hod_broadcasts.html', broadcasts=broadcasts)


@hod_bp.route('/hod/broadcasts/<int:id>/delete', methods=['POST'])
@login_required
@role_required('HOD')
def delete_dept_broadcast(id):
    from models import Broadcast
    broadcast = Broadcast.query.get_or_404(id)
    hod = current_user.hod_profile
    
    if broadcast.scope != 'department' or broadcast.department != hod.department:
        flash('Unauthorized', 'danger')
        return redirect(url_for('hod.manage_dept_broadcasts'))
    
    db.session.delete(broadcast)
    db.session.commit()
    flash('Broadcast deleted', 'success')
    return redirect(url_for('hod.manage_dept_broadcasts'))


@hod_bp.route('/hod/broadcasts/<int:id>/pin', methods=['POST'])
@login_required
@role_required('HOD')
def pin_dept_broadcast(id):
    from models import Broadcast
    broadcast = Broadcast.query.get_or_404(id)
    hod = current_user.hod_profile
    
    if broadcast.scope != 'department' or broadcast.department != hod.department:
        flash('Unauthorized', 'danger')
        return redirect(url_for('hod.manage_dept_broadcasts'))
    
    broadcast.is_pinned = not broadcast.is_pinned
    db.session.commit()
    flash(f'Broadcast {"pinned" if broadcast.is_pinned else "unpinned"}', 'success')
    return redirect(url_for('hod.manage_dept_broadcasts'))