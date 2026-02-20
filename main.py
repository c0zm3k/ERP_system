from fastapi import FastAPI, Request, Depends, HTTPException, status, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import date, datetime, timedelta
from typing import Optional, List
from jose import JWTError, jwt
from passlib.context import CryptContext
import os

from models import db, User, StudentDetails, FacultyDetails, HODDetails, Leaves, Event, Fee, ClassAllotment, Attendance, Certificate
from schemas import UserSchema, LeaveSchema, EventSchema
from extensions import db as flask_db

# Security Configuration
SECRET_KEY = "LUMEN_ERP_FASTAPI_SECRET" # Should be env var in production
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 600

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

app = FastAPI(title="Lumen ERP - FastAPI")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Password Utilities
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

# JWT Utilities
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# Dependency: Get Current User from Cookie (for browser auth)
async def get_current_user_from_cookie(request: Request):
    token = request.cookies.get("access_token")
    if not token:
        return None
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            return None
        # Bridging Flask-SQLAlchemy session
        user = User.query.filter_by(username=username).first()
        return user
    except JWTError:
        return None

@app.get("/", response_class=HTMLResponse)
async def index(request: Request, current_user: User = Depends(get_current_user_from_cookie)):
    if current_user:
        return RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)
    return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

@app.get("/login", response_class=HTMLResponse)
async def login_get(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
async def login_post(request: Request, username: str = Form(...), password: str = Form(...)):
    user = User.query.filter_by(username=username).first()
    if not user or not user.check_password(password):
        # Flash message logic (simplified for FastAPI templates)
        return templates.TemplateResponse("login.html", {"request": request, "error": "Invalid credentials"})
    
    access_token = create_access_token(data={"sub": user.username})
    response = RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(key="access_token", value=access_token, httponly=True)
    return response

@app.post("/logout")
async def logout():
    response = RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie("access_token")
    return response

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, current_user: User = Depends(get_current_user_from_cookie)):
    if not current_user:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    
    events = Event.query.all()
    # Leave Stats
    total_leaves = 15 # Example policy
    used_leaves = Leaves.query.filter_by(user_id=current_user.id, status='Approved').count()
    leaves_left = total_leaves - used_leaves
    
    return templates.TemplateResponse("dashboard.html", {
        "request": request, 
        "current_user": current_user,
        "events": events,
        "total_leaves": total_leaves,
        "leaves_left": leaves_left
    })

# Leave Request Logic
@app.post("/leaves/request")
async def request_leave(
    request: Request, 
    leave_type: str = Form(...), 
    from_date: date = Form(...), 
    to_date: date = Form(...), 
    reason: str = Form(...),
    current_user: User = Depends(get_current_user_from_cookie)
):
    if not current_user:
        raise HTTPException(status_code=401)
    
    new_leave = Leaves(
        user_id=current_user.id,
        type=leave_type,
        start_date=from_date,
        end_date=to_date,
        reason=reason,
        status='Pending'
    )
    flask_db.session.add(new_leave)
    flask_db.session.commit()
    return RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)

# Approval Machine
@app.post("/leaves/approve/{leave_id}")
async def approve_leave(leave_id: int, current_user: User = Depends(get_current_user_from_cookie)):
    leave = Leaves.query.get(leave_id)
    applicant = leave.user
    
    # Student -> Faculty -> HOD
    if applicant.role == 'Student':
        if current_user.role == 'Faculty' and leave.status == 'Pending':
            leave.status = 'Faculty_Approved'
        elif current_user.role == 'HOD' and leave.status == 'Faculty_Approved':
            leave.status = 'Approved'
        else:
            raise HTTPException(status_code=403, detail="Invalid approval sequence")
            
    # Faculty -> HOD -> Admin
    elif applicant.role == 'Faculty':
        if current_user.role == 'HOD' and leave.status == 'Pending':
            leave.status = 'HOD_Approved'
        elif (current_user.role == 'Admin' or (current_user.role == 'Asst_HOD' and is_admin_on_leave())) and leave.status == 'HOD_Approved':
            leave.status = 'Approved'
        else:
            raise HTTPException(status_code=403)

    # HOD -> Admin
    elif applicant.role == 'HOD':
        if (current_user.role == 'Admin' or (current_user.role == 'Asst_HOD' and is_admin_on_leave())) and leave.status == 'Pending':
            leave.status = 'Approved'
            
    flask_db.session.commit()
    return RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)

@app.post("/leaves/reject/{leave_id}")
async def reject_leave(leave_id: int, current_user: User = Depends(get_current_user_from_cookie)):
    if not current_user:
        raise HTTPException(status_code=401)
        
    leave = Leaves.query.get(leave_id)
    if not leave:
        raise HTTPException(status_code=404)
        
    # Permission logic for Revocation (similar to Approval)
    applicant = leave.user
    can_reject = False
    
    if applicant.role == 'Student' and current_user.role in ['Faculty', 'HOD']:
        can_reject = True
    elif applicant.role == 'Faculty' and (current_user.role == 'HOD' or current_user.role == 'Admin' or (current_user.role == 'Asst_HOD' and is_admin_on_leave())):
        can_reject = True
    elif applicant.role == 'HOD' and (current_user.role == 'Admin' or (current_user.role == 'Asst_HOD' and is_admin_on_leave())):
        can_reject = True
        
    if not can_reject:
        raise HTTPException(status_code=403, detail="Unauthorized revocation attempt")
        
    leave.status = 'Revoked'
    flask_db.session.commit()
    return RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)

def is_admin_on_leave():
    admin = User.query.filter_by(role='Admin').first()
    if not admin: return False
    active_leave = Leaves.query.filter_by(user_id=admin.id, status='Approved').filter(
        Leaves.start_date <= date.today(),
        Leaves.end_date >= date.today()
    ).first()
    return active_leave is not None

@app.get("/admin", response_class=HTMLResponse)
async def admin_panel(request: Request, current_user: User = Depends(get_current_user_from_cookie)):
    if not current_user or current_user.role not in ['Admin', 'HOD', 'Asst_HOD']:
        return RedirectResponse(url="/login")
    
    # Hierarchy Sorting: Admin > HOD > Asst_HOD > Faculty
    role_order = {'Admin': 1, 'HOD': 2, 'Asst_HOD': 3, 'Faculty': 4}
    all_faculties = User.query.filter(User.role.in_(['HOD', 'Asst_HOD', 'Faculty'])).all()
    faculties_sorted = sorted(all_faculties, key=lambda x: (x.department or '', role_order.get(x.role, 5)))
    
    return templates.TemplateResponse("admin_panel.html", {
        "request": request, 
        "current_user": current_user, 
        "faculties_sorted": faculties_sorted
    })

@app.get("/admin/users", response_class=HTMLResponse)
async def manage_users_get(request: Request, current_user: User = Depends(get_current_user_from_cookie)):
    if not current_user or current_user.role not in ['Admin', 'HOD']:
        return RedirectResponse(url="/login")
    
    users = User.query.all()
    hods = User.query.filter_by(role='HOD').all()
    return templates.TemplateResponse("manage_users.html", {
        "request": request, 
        "current_user": current_user, 
        "users": users,
        "hods": hods
    })

@app.post("/admin/users")
async def manage_users_post(
    request: Request, 
    username: str = Form(...), 
    password: str = Form(...), 
    role: str = Form(...),
    hod_id: Optional[int] = Form(None),
    enrollment_no: Optional[str] = Form(None),
    semester: Optional[int] = Form(None),
    current_user: User = Depends(get_current_user_from_cookie)
):
    if not current_user or current_user.role not in ['Admin', 'HOD']:
        raise HTTPException(status_code=403)
        
    new_user = User(username=username, role=role)
    new_user.set_password(password)
    flask_db.session.add(new_user)
    flask_db.session.flush()

    if role == 'HOD':
        hod = HODDetails(user_id=new_user.id, department='General')
        flask_db.session.add(hod)
    elif role == 'Faculty':
        fac = FacultyDetails(user_id=new_user.id, department='General', designation='Lecturer', hod_id=hod_id)
        flask_db.session.add(fac)
    elif role == 'Student':
        stu = StudentDetails(user_id=new_user.id, enrollment_no=enrollment_no, semester=semester)
        flask_db.session.add(stu)
        
    flask_db.session.commit()
    return RedirectResponse(url="/admin/users", status_code=status.HTTP_303_SEE_OTHER)

@app.get("/admin/allot_class", response_class=HTMLResponse)
async def allot_class_get(request: Request, current_user: User = Depends(get_current_user_from_cookie)):
    if not current_user or current_user.role not in ['Admin', 'HOD']:
        return RedirectResponse(url="/login")
    
    faculties = FacultyDetails.query.all()
    allotments = ClassAllotment.query.all()
    return templates.TemplateResponse("allot_classes.html", {
        "request": request, 
        "current_user": current_user, 
        "faculties": faculties,
        "allotments": allotments
    })

@app.post("/admin/allot_class")
async def allot_class_post(
    faculty_id: int = Form(...),
    subject: str = Form(...),
    department: str = Form(...),
    class_name: str = Form(...),
    current_user: User = Depends(get_current_user_from_cookie)
):
    allotment = ClassAllotment(faculty_id=faculty_id, subject=subject, department=department, class_name=class_name)
    flask_db.session.add(allotment)
    flask_db.session.commit()
    return RedirectResponse(url="/admin/allot_class", status_code=status.HTTP_303_SEE_OTHER)

@app.post("/admin/events/add")
async def add_event(
    title: str = Form(...),
    event_date: date = Form(...),
    description: str = Form(...),
    current_user: User = Depends(get_current_user_from_cookie)
):
    if not current_user or current_user.role != 'Admin':
        raise HTTPException(status_code=403)
    
    new_event = Event(title=title, event_date=event_date, description=description)
    flask_db.session.add(new_event)
    flask_db.session.commit()
    return RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)

@app.get("/attendance", response_class=HTMLResponse)
async def mark_attendance_get(request: Request, current_user: User = Depends(get_current_user_from_cookie)):
    if not current_user or current_user.role != 'Faculty':
        return RedirectResponse(url="/dashboard")
    
    faculty = current_user.faculty_profile
    allotments = faculty.allotments.all()
    return templates.TemplateResponse("attendance.html", {"request": request, "current_user": current_user, "allotments": allotments})


@app.get("/fees", response_class=HTMLResponse)
async def view_fees(request: Request, current_user: User = Depends(get_current_user_from_cookie)):
    if not current_user:
        return RedirectResponse(url="/login")
    
    if current_user.role == 'Student':
        fees = current_user.student_profile.fees.all()
    else:
        fees = Fee.query.all()
    return templates.TemplateResponse("fees.html", {"request": request, "current_user": current_user, "fees": fees})

@app.get("/certificates", response_class=HTMLResponse)
async def view_certificates(request: Request, current_user: User = Depends(get_current_user_from_cookie)):
    if not current_user:
        return RedirectResponse(url="/login")
    
    if current_user.role == 'Student':
        certs = current_user.student_profile.certificates.all()
    else:
        certs = Certificate.query.all()
    return templates.TemplateResponse("certificates.html", {"request": request, "current_user": current_user, "certificates": certs})

@app.get("/leaves", response_class=HTMLResponse)
async def leaves_get(request: Request, current_user: User = Depends(get_current_user_from_cookie)):
    if not current_user:
        return RedirectResponse(url="/login")
    
    if current_user.role == 'Admin':
        all_leaves = Leaves.query.all()
    elif current_user.role == 'HOD':
        # See dept leaves
        all_leaves = Leaves.query.join(User).filter(User.department == current_user.department).all()
    elif current_user.role == 'Faculty':
        # See student leaves for assigned students
        all_leaves = Leaves.query.join(User).join(StudentDetails, User.id == StudentDetails.user_id).filter(StudentDetails.faculty_id == current_user.faculty_profile.id).all()
    else:
        all_leaves = current_user.leaves.all()
        
    return templates.TemplateResponse("leaves.html", {"request": request, "current_user": current_user, "leaves": all_leaves})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
