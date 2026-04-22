from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class Token(BaseModel):
    access_token: str
    token_type: str


class UserCreate(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    id: int
    username: str
    is_admin: bool

    class Config:
        from_attributes = True


class DocumentOut(BaseModel):
    id: int
    filename: str
    content: Optional[str] = None
    uploaded_at: datetime

    class Config:
        from_attributes = True


class DocumentList(BaseModel):
    id: int
    filename: str
    uploaded_at: datetime

    class Config:
        from_attributes = True


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    response: str


# -----------------------
# Interview schemas
# -----------------------

class InterviewStartResponse(BaseModel):
    applicant_id: int
    greeting: str


class InterviewChatRequest(BaseModel):
    message: str


class InterviewChatResponse(BaseModel):
    response: str
    interview_complete: bool


class InterviewStatus(BaseModel):
    id: int
    name: str
    program: str
    is_complete: bool
    created_at: datetime

    class Config:
        from_attributes = True


class ChatMessageOut(BaseModel):
    role: str
    content: str
    created_at: datetime

    class Config:
        from_attributes = True


# -----------------------
# Admin schemas
# -----------------------

class AdminApplicantListItem(BaseModel):
    id: int
    name: str
    program: str
    is_complete: bool
    created_at: datetime
    outcome: Optional[str] = None

    class Config:
        from_attributes = True


class AdminAssessmentOut(BaseModel):
    outcome: str
    rule_summary: Optional[str] = None
    transcript: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class AdminApplicantDetail(BaseModel):
    id: int
    name: str
    program: str
    details: Optional[dict] = None
    is_complete: bool
    created_at: datetime
    assessment: Optional[AdminAssessmentOut] = None

    class Config:
        from_attributes = True


class AdminTranscriptMessage(BaseModel):
    role: str
    content: str
    created_at: datetime

    class Config:
        from_attributes = True


class AdminDocumentItem(BaseModel):
    id: int
    filename: str
    uploaded_at: datetime
    is_active: bool

    class Config:
        from_attributes = True
