"""Shared ORM metadata without configuration or database bootstrap."""
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
