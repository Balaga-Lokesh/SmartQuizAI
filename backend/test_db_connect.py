# test_db_connect.py
from sqlalchemy import create_engine, text
from app.core.config import settings

print("Using DB URL:", settings.DATABASE_URL)
engine = create_engine(settings.DATABASE_URL, future=True)
with engine.connect() as conn:
    r = conn.execute(text("SELECT 1"))
    print("DB test result:", r.scalar())
