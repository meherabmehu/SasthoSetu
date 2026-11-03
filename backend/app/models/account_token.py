"""Hashed, expiring, single-use account credentials. Raw tokens are never stored."""
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String

from app.models.base import Base


class AccountToken(Base):
    __tablename__ = "account_tokens"

    token_hash = Column(String(64), primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    purpose = Column(String(16), nullable=False)
    token_version = Column(Integer, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    consumed_at = Column(DateTime(timezone=True), nullable=True)
