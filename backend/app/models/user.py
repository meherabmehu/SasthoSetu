import uuid

from sqlalchemy import Column
from sqlalchemy import String
from sqlalchemy import Boolean

from app.models.base import Base


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    full_name = Column(String, nullable=False)

    email = Column(String, unique=True, nullable=False)

    phone = Column(String, unique=True, nullable=False)

    password_hash = Column(String, nullable=False)

    is_active = Column(Boolean, default=True)

    is_verified = Column(Boolean, default=False)