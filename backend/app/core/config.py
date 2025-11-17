# backend/app/core/config.py
import os
from pathlib import Path
from urllib.parse import quote_plus
from dotenv import load_dotenv
load_dotenv()

# Load env files (without modifying them)
try:
    from dotenv import load_dotenv
except Exception as e:
    raise RuntimeError("python-dotenv is required. Run: pip install python-dotenv") from e

ROOT = Path(__file__).resolve().parents[2]  # backend/
# Try env files in order of precedence but DO NOT write or change them.
for name in (".env.local", ".env", ".env.example"):
    candidate = ROOT / name
    if candidate.exists():
        load_dotenv(candidate)
        break
# If none exists, we still rely on system environment variables.

# Read raw env vars (your .env contains separate vars)
_env = os.environ

# If DATABASE_URL already present in env, use it. Otherwise compose from components.
DATABASE_URL = _env.get("DATABASE_URL")
if not DATABASE_URL:
    # Required components (some may be missing; we provide safe defaults)
    DB_DRIVER = _env.get("DB_DRIVER", "mysql+mysqlconnector")
    DB_USER = _env.get("DB_USER", "smartquiz")
    DB_PASS = _env.get("DB_PASS", "smartquiz_pass")
    DB_HOST = _env.get("DB_HOST", "127.0.0.1")
    DB_PORT = _env.get("DB_PORT", "3306")
    DB_NAME = _env.get("DB_NAME", "smartquiz")

    # URL-escape username/password
    user_quoted = quote_plus(DB_USER)
    pass_quoted = quote_plus(DB_PASS)

    # Build: driver://user:pass@host:port/dbname
    DATABASE_URL = f"{DB_DRIVER}://{user_quoted}:{pass_quoted}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Redis and optional secrets
REDIS_URL = _env.get("REDIS_URL", "redis://127.0.0.1:6379/0")
JWT_SECRET = _env.get("JWT_SECRET")  # optional


# For compatibility with the rest of the code that expects a Settings object,
# provide a tiny class with attributes. We purposely do NOT require pydantic here
# so this works even if pydantic settings are not installed/compatible.
class SimpleSettings:
    DATABASE_URL = DATABASE_URL
    REDIS_URL = REDIS_URL
    JWT_SECRET = JWT_SECRET


settings = SimpleSettings()
