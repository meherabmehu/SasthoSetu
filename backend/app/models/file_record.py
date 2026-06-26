import uuid

from sqlalchemy import Column
from sqlalchemy import String

from app.models.base import Base


class FileRecord(Base):
    __tablename__ = "file_records"

    id = Column(
        String,
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )

    patient_id = Column(
        String,
        nullable=False
    )

    uploaded_by = Column(
        String,
        nullable=False
    )

    file_name = Column(
        String,
        nullable=False
    )

    file_path = Column(
        String,
        nullable=False
    )

    file_type = Column(
        String,
        nullable=False
    )