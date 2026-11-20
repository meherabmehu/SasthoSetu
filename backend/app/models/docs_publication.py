"""Persistent configuration for the public SasthoSetu documentation hub."""
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, Text

from app.models.base import Base


class DocsPublication(Base):
    __tablename__ = "docs_publications"

    id = Column(Integer, primary_key=True, default=1)
    public_enabled = Column(Boolean, nullable=False, default=True)
    starts_at = Column(DateTime(timezone=True), nullable=True)
    ends_at = Column(DateTime(timezone=True), nullable=True)
    content_json = Column(Text, nullable=False, default="{}")
    version = Column(Integer, nullable=False, default=1)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)


class DocsPublicationVersion(Base):
    __tablename__ = "docs_publication_versions"

    id = Column(Integer, primary_key=True)
    publication_id = Column(Integer, nullable=False, index=True)
    version = Column(Integer, nullable=False)
    content_json = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    created_by = Column(Text, nullable=True)
