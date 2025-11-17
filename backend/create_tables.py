# create_tables.py
from app.models import Base
from app.db.session import engine

Base.metadata.create_all(bind=engine)
print("All tables created.")
