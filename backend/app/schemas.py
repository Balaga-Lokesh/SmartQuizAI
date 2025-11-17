# backend/app/schemas.py
from pydantic import BaseModel, EmailStr, ConfigDict
from typing import Optional, List
from datetime import datetime

class UserCreate(BaseModel):
    email: EmailStr
    full_name: Optional[str]
    password: str

class UserOut(BaseModel):
    id: int
    email: EmailStr
    full_name: Optional[str]
    role: str
    is_active: bool
    created_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)

class QuizCreate(BaseModel):
    title: str
    topic: Optional[str]
    description: Optional[str]
    difficulty: Optional[str] = "any"

class QuestionOut(BaseModel):
    id: int
    text: str
    option_a: Optional[str]
    option_b: Optional[str]
    option_c: Optional[str]
    option_d: Optional[str]
    correct_option: Optional[str] = None
    explanation: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

class QuizOut(BaseModel):
    id: int
    title: str
    topic: Optional[str]
    description: Optional[str]
    difficulty: Optional[str]
    status: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

class QuizDetail(QuizOut):
    questions: List[QuestionOut]

class AnswerItem(BaseModel):
    question_id: int
    chosen_option: str  # 'a'|'b'|'c'|'d'

class SubmitAnswers(BaseModel):
    answers: List[AnswerItem]
