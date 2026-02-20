from pydantic import BaseModel, ConfigDict
from datetime import date, datetime
from typing import Optional, List

class UserBase(BaseModel):
    username: str
    role: str

class UserCreate(UserBase):
    password: str

class UserSchema(UserBase):
    id: int
    image_file: str
    department: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

class LeaveBase(BaseModel):
    type: str
    reason: str
    start_date: date
    end_date: date

class LeaveCreate(LeaveBase):
    pass

class LeaveSchema(LeaveBase):
    id: int
    user_id: int
    status: str
    date_submitted: datetime
    model_config = ConfigDict(from_attributes=True)

class EventBase(BaseModel):
    title: str
    description: Optional[str] = None
    event_date: date

class EventSchema(EventBase):
    id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class FeeSchema(BaseModel):
    id: int
    title: str
    amount: float
    due_date: date
    status: str
    semester: int
    model_config = ConfigDict(from_attributes=True)
