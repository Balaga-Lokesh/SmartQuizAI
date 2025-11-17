# backend/app/api/v1/quizzes.py
import os
import glob
import shutil
import traceback
from uuid import uuid4
from typing import List, Optional, Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, UploadFile, File, Form
from sqlalchemy.orm import Session

from app.db.session import get_db, SessionLocal
from app.models import Quiz, Question, User, QuizStatusEnum
from app.schemas import QuizOut, QuizDetail
from app.api.v1.auth import get_current_user

# Import your generator (may accept file_path: str and model_override kw)
generate_quiz_from_file = None
try:
    from app.services.ai_generator import generate_quiz_from_file
except Exception:
    generate_quiz_from_file = None

router = APIRouter(prefix="/quizzes", tags=["quizzes"])


def assert_teacher(user: User):
    if not user or getattr(user, "role", "").lower() != "teacher":
        raise HTTPException(status_code=403, detail="Teacher privileges required")


# -----------------------
# Background worker (fixed to call generator correctly)
# -----------------------
def _background_generate_quiz_from_files(quiz_id: int, files_paths: List[str], metadata: dict):
    """
    Background task that calls the AI generator and persists questions.
    IMPORTANT: Calls generate_quiz_from_file with single file_path and model_override kw,
    because your generator expects a single path and 'model_override' parameter.
    """
    db = SessionLocal()
    try:
        quiz = db.query(Quiz).filter(Quiz.id == quiz_id).first()
        if not quiz:
            print(f"[AI-Gen-file] quiz {quiz_id} not found (background).")
            return

        if not generate_quiz_from_file:
            # generator not available — mark draft and return
            quiz.status = QuizStatusEnum.draft
            db.add(quiz)
            db.commit()
            print("[AI-Gen-file] generator-from-file not available.")
            return

        # Use only the first uploaded file to match generator signature
        if not files_paths:
            quiz.status = QuizStatusEnum.draft
            db.add(quiz)
            db.commit()
            print(f"[AI-Gen-file] no files for quiz {quiz_id}")
            return

        first_file = files_paths[0]

        try:
            # call generator using the exact kw the ai_generator expects
            questions = generate_quiz_from_file(
                file_path=first_file,
                title=metadata.get("title"),
                topic=metadata.get("topic"),
                difficulty=metadata.get("difficulty", "any"),
                num_questions=metadata.get("num_questions", 5),
                model_override=metadata.get("model"),
            )
        except TypeError as te:
            # If generator has slightly different kw names, attempt fallback mapping attempts:
            print(f"[AI-Gen-file] TypeError: {te} — attempting fallback calls")
            try:
                # Try alternate kw name `model` if generator expects it
                questions = generate_quiz_from_file(
                    file_path=first_file,
                    title=metadata.get("title"),
                    topic=metadata.get("topic"),
                    difficulty=metadata.get("difficulty", "any"),
                    num_questions=metadata.get("num_questions", 5),
                    model=metadata.get("model"),
                )
            except Exception as e:
                quiz.status = QuizStatusEnum.draft
                db.add(quiz)
                db.commit()
                print(f"[AI-Gen-file] generation FAILED on fallback: {e}")
                traceback.print_exc()
                return
        except Exception as e:
            quiz.status = QuizStatusEnum.draft
            db.add(quiz)
            db.commit()
            print(f"[AI-Gen-file] generation FAILED: {e}")
            traceback.print_exc()
            return

        # Validate output
        if not isinstance(questions, list):
            print(f"[AI-Gen-file] invalid generator output type for quiz {quiz_id} (expected list)")
            quiz.status = QuizStatusEnum.draft
            db.add(quiz)
            db.commit()
            return

        # Save questions to DB
        saved_count = 0
        for q in questions:
            try:
                question = Question(
                    quiz_id=quiz.id,
                    text=q.get("text") or q.get("question") or "",
                    option_a=q.get("option_a") or q.get("a"),
                    option_b=q.get("option_b") or q.get("b"),
                    option_c=q.get("option_c") or q.get("c"),
                    option_d=q.get("option_d") or q.get("d"),
                    correct_option=(q.get("correct_option") or q.get("correct") or "a").lower(),
                    explanation=q.get("explanation", ""),
                    ai_generated=True,
                )
                db.add(question)
                saved_count += 1
            except Exception as e:
                print(f"[AI-Gen-file] skip invalid question data: {e}")
                continue

        quiz.status = QuizStatusEnum.ready
        db.add(quiz)
        db.commit()
        print(f"[AI-Gen-file] SUCCESS: quiz {quiz_id} generated with {saved_count} questions.")

    except Exception as e:
        print(f"[AI-Gen-file] CRASH: {e}")
        traceback.print_exc()
    finally:
        db.close()


# -----------------------
# Endpoints
# -----------------------

@router.get("/my", response_model=List[QuizOut])
def get_my_quizzes(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Return quizzes created by the current teacher (most recent first).
    Endpoint: GET /api/v1/quizzes/my
    """
    if not current_user or getattr(current_user, "role", "").lower() != "teacher":
        raise HTTPException(status_code=403, detail="Only teachers can access this endpoint")

    quizzes = db.query(Quiz).filter(Quiz.creator_id == current_user.id).order_by(Quiz.created_at.desc()).all()
    return quizzes


@router.get("/", response_model=List[QuizOut])
def list_ready_quizzes(db: Session = Depends(get_db)):
    quizzes = db.query(Quiz).filter(Quiz.status == QuizStatusEnum.ready).order_by(Quiz.created_at.desc()).all()
    return quizzes


@router.get("/{quiz_id}", response_model=QuizDetail)
def get_quiz_detail(quiz_id: int, current_user: Optional[User] = Depends(get_current_user), db: Session = Depends(get_db)):
    quiz = db.query(Quiz).filter(Quiz.id == quiz_id).first()
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")
    if quiz.status != QuizStatusEnum.ready:
        if not current_user:
            raise HTTPException(status_code=403, detail="Not authorized to view this quiz")
        if current_user.role.lower() != "teacher" and quiz.creator_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not authorized to view this quiz")
    return quiz


@router.get("/{quiz_id}/status")
def get_quiz_status(quiz_id: int, db: Session = Depends(get_db)):
    quiz = db.query(Quiz).filter(Quiz.id == quiz_id).first()
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")
    return {"quiz_id": quiz_id, "status": quiz.status.value if hasattr(quiz.status, "value") else str(quiz.status)}


@router.post("/generate-from-file", status_code=status.HTTP_201_CREATED)
def generate_quiz_from_file_endpoint(
    background_tasks: BackgroundTasks,
    title: str = Form(...),
    topic: str = Form(...),
    difficulty: str = Form("any"),
    num_questions: int = Form(5),
    model: Optional[str] = Form(None),
    files: List[UploadFile] = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    assert_teacher(current_user)

    if not files or len(files) == 0:
        raise HTTPException(status_code=400, detail="No files uploaded")

    if len(files) > 10:
        raise HTTPException(status_code=400, detail="Too many files. Max allowed is 10.")

    uploads_root = os.path.join(os.getcwd(), "uploads")
    os.makedirs(uploads_root, exist_ok=True)

    try:
        quiz = Quiz(
            creator_id=current_user.id,
            title=title,
            topic=topic,
            description=f"AI-generated from uploaded file(s)",
            difficulty=difficulty,
            status=QuizStatusEnum.generating,
        )
        db.add(quiz)
        db.commit()
        db.refresh(quiz)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB error: {e}")

    quiz_id = quiz.id
    quiz_dir = os.path.join(uploads_root, f"teacher_{current_user.id}", str(uuid4().hex))
    os.makedirs(quiz_dir, exist_ok=True)

    saved_paths = []
    try:
        for f in files:
            safe_name = f.filename.replace("..", "_")
            dest = os.path.join(quiz_dir, safe_name)
            with open(dest, "wb") as out_f:
                shutil.copyfileobj(f.file, out_f)
            saved_paths.append(dest)
    except Exception as e:
        quiz.status = QuizStatusEnum.draft
        db.add(quiz)
        db.commit()
        raise HTTPException(status_code=500, detail=f"Failed saving files: {e}")

    metadata = {
        "title": title,
        "topic": topic,
        "num_questions": num_questions,
        "difficulty": difficulty,
        "model": model,
        "uploader": current_user.id,
    }

    background_tasks.add_task(_background_generate_quiz_from_files, quiz_id, saved_paths, metadata)

    return {"quiz_id": quiz_id, "status": "generating"}


# -----------------------
# Teacher: rebuild endpoint (re-run generation using saved uploads)
# -----------------------
@router.post("/{quiz_id}/rebuild", status_code=status.HTTP_202_ACCEPTED)
def rebuild_quiz_generation(quiz_id: int, background_tasks: BackgroundTasks, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Teacher-only: re-run AI generation for an existing quiz.
    Strategy:
      - find uploads/teacher_{creator_id}/* folders and pick most recent folder (assumes the latest upload corresponds to the quiz).
      - set quiz.status = generating, then schedule background task with found file paths.
    """
    # Permission + existence checks
    quiz = db.query(Quiz).filter(Quiz.id == quiz_id).first()
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")
    if current_user.role.lower() != "teacher" and quiz.creator_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    # Look for saved files under uploads/teacher_{creator_id}/
    uploads_root = os.path.join(os.getcwd(), "uploads")
    teacher_dir = os.path.join(uploads_root, f"teacher_{current_user.id}")
    if not os.path.isdir(teacher_dir):
        raise HTTPException(status_code=400, detail="No uploaded files found for this teacher")

    # pick newest subdirectory (most recently modified)
    subdirs = [os.path.join(teacher_dir, d) for d in os.listdir(teacher_dir) if os.path.isdir(os.path.join(teacher_dir, d))]
    if not subdirs:
        raise HTTPException(status_code=400, detail="No upload folders found for this teacher")

    # sort by modification time desc
    subdirs.sort(key=lambda p: os.path.getmtime(p), reverse=True)

    # find the best candidate folder that contains PDFs
    candidate = None
    candidate_files = []
    for d in subdirs:
        pdfs = glob.glob(os.path.join(d, "*.pdf"))
        if pdfs:
            candidate = d
            candidate_files = pdfs
            break

    if not candidate:
        raise HTTPException(status_code=400, detail="No uploaded PDF files found for this teacher's folders")

    # Update quiz status and schedule re-generation using the found files
    quiz.status = QuizStatusEnum.generating
    db.add(quiz)
    db.commit()

    # Schedule the background job
    background_tasks.add_task(_background_generate_quiz_from_files, quiz_id, candidate_files, {
        "title": quiz.title,
        "topic": quiz.topic,
        "num_questions": 10,
        "difficulty": quiz.difficulty,
        "model": None,
    })

    return {"quiz_id": quiz_id, "status": "restarted", "used_folder": candidate, "files_count": len(candidate_files)}
