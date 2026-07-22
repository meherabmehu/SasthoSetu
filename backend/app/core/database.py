# -*- coding: utf-8 -*-
"""SQLAlchemy engine / session / base."""
from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import get_settings

settings = get_settings()

_connect_args = ({"check_same_thread": False}
                 if settings.DATABASE_URL.startswith("sqlite") else {})

engine = create_engine(settings.DATABASE_URL, connect_args=_connect_args,
                       pool_pre_ping=True)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
