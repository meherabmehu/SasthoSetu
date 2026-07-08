import uuid

from sqlalchemy import Column
from sqlalchemy import String
from sqlalchemy import Boolean
from sqlalchemy import false
from sqlalchemy import true

from app.models.base import Base


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    full_name = Column(String, nullable=False)

    email = Column(String, unique=True, nullable=False)

    phone = Column(String, unique=True, nullable=False)

    password_hash = Column(String, nullable=False)

    is_active = Column(
        Boolean,
        default=True,
        server_default=true(),
    )

    is_verified = Column(
        Boolean,
        default=False,
        server_default=false(),
    )
    role = Column(
        String,
        nullable=False,
        default="PATIENT",
        server_default="PATIENT",
    )
