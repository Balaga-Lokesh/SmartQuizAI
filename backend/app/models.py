# backend/app/models.py
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, Enum, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship, backref
from app.db.session import Base
import enum

class RoleEnum(str, enum.Enum):
    student = "student"
    teacher = "teacher"
    admin = "admin"

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(512), nullable=False)
    full_name = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=False)
    role = Column(String(50), default=RoleEnum.student.value)
    created_at = Column(DateTime, default=datetime.utcnow)

    quizzes = relationship("Quiz", back_populates="creator")

    def __repr__(self):
        return f"<User id={self.id} email={self.email} role={self.role}>"

class QuizStatusEnum(str, enum.Enum):
    draft = "draft"
    generating = "generating"
    ready = "ready"

class Quiz(Base):
    __tablename__ = "quizzes"
    id = Column(Integer, primary_key=True, index=True)
    creator_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(255), nullable=False)
    topic = Column(Text, nullable=True)
    description = Column(Text, nullable=True)
    status = Column(Enum(QuizStatusEnum), default=QuizStatusEnum.draft)
    difficulty = Column(String(20), default="any")
    created_at = Column(DateTime, server_default=func.now())

    creator = relationship("User", back_populates="quizzes")
    questions = relationship("Question", back_populates="quiz", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Quiz id={self.id} title={self.title} status={self.status}>"

class Question(Base):
    __tablename__ = "questions"
    id = Column(Integer, primary_key=True, index=True)
    quiz_id = Column(Integer, ForeignKey("quizzes.id", ondelete="CASCADE"), nullable=False)
    text = Column(Text, nullable=False)
    option_a = Column(Text)
    option_b = Column(Text)
    option_c = Column(Text)
    option_d = Column(Text)
    correct_option = Column(String(1), nullable=False)
    explanation = Column(Text)
    ai_generated = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())

    quiz = relationship("Quiz", back_populates="questions")

    def __repr__(self):
        return f"<Question id={self.id} quiz_id={self.quiz_id}>"

class EmailOTP(Base):
    __tablename__ = "email_otps"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    email = Column(String(255), index=True, nullable=False)
    code = Column(String(512), nullable=False)  # will hold "hash|salt"
    used = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)

    user = relationship("User", backref=backref("otps", cascade="all, delete-orphan"))

class Response(Base):
    __tablename__ = "responses"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    quiz_id = Column(Integer, ForeignKey("quizzes.id", ondelete="CASCADE"), nullable=False)
    question_id = Column(Integer, ForeignKey("questions.id", ondelete="CASCADE"), nullable=False)
    chosen_option = Column(String(1), nullable=False)  # 'a','b','c','d'
    is_correct = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())

    user = relationship("User", backref=backref("responses", cascade="all, delete-orphan"))
    quiz = relationship("Quiz", backref=backref("responses", cascade="all, delete-orphan"))
    question = relationship("Question")
