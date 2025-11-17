# app/main.py
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import traceback
import sys
from typing import List

# import your routers
from app.api.v1 import users, auth, protected, quizzes

# import DB Base so we can create tables on startup
from app.db.session import Base, engine

app = FastAPI(title="SmartQuiz AI - Backend (local)")

# CORS - allow your frontend origin(s)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # change for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(Exception)
async def all_exception_handler(request: Request, exc: Exception):
    # Print traceback to stderr for visibility in dev
    print("=== Unhandled exception during request ===", file=sys.stderr)
    traceback.print_exc()
    # Return a sanitized error message to the client
    return JSONResponse(status_code=500, content={"detail": "Internal Server Error", "error": str(exc)})

# include routers under /api/v1
app.include_router(users.router, prefix="/api/v1")
app.include_router(auth.router, prefix="/api/v1")
app.include_router(protected.router, prefix="/api/v1")
app.include_router(quizzes.router, prefix="/api/v1")

@app.on_event("startup")
def startup_event():
    try:
        # Create DB tables if they don't exist (good for local/dev)
        Base.metadata.create_all(bind=engine)
        print("Database tables created/checked.")
    except Exception as e:
        print("Error creating tables on startup:", e)
