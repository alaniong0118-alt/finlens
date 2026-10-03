from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker


import os

from app.config import load_backend_env

load_backend_env()
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
if not DATABASE_URL:
    raise RuntimeError("Set DATABASE_URL privately in backend/.env or the process environment.")


class Base(DeclarativeBase):
    pass


engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
)


SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)