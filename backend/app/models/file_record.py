import uuid

from sqlalchemy import Column
from sqlalchemy import Integer
from sqlalchemy import LargeBinary
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

    # Kept only for rows written when uploads went to a local directory.
    # New uploads leave it empty and store the bytes in `content`.
    file_path = Column(
        String,
        nullable=True
    )

    content = Column(
        LargeBinary,
        nullable=True
    )

    file_size = Column(
        Integer,
        nullable=True
    )

    file_type = Column(
        String,
        nullable=False
    )