import os

from fastapi import UploadFile
from fastapi import HTTPException

from sqlalchemy.orm import Session

from app.models.patient import Patient
from app.models.file_record import FileRecord


UPLOAD_DIR = "uploads"

os.makedirs(
    UPLOAD_DIR,
    exist_ok=True
)


def upload_file_service(
    patient_user_id: str,
    file: UploadFile,
    db: Session
):

    patient = (
        db.query(Patient)
        .filter(
            Patient.user_id == patient_user_id
        )
        .first()
    )

    if not patient:
        raise HTTPException(
            status_code=404,
            detail="Patient not found"
        )

    file_path = os.path.join(
        UPLOAD_DIR,
        file.filename
    )

    with open(
        file_path,
        "wb"
    ) as buffer:
        buffer.write(
            file.file.read()
        )

    record = FileRecord(
        patient_id=patient.id,
        uploaded_by=patient_user_id,
        file_name=file.filename,
        file_path=file_path,
        file_type=file.content_type
    )

    db.add(record)
    db.commit()

    return {
        "message": "File uploaded successfully",
        "file_name": file.filename
    }


def get_patient_files_service(
    patient_user_id: str,
    db: Session
):

    patient = (
        db.query(Patient)
        .filter(
            Patient.user_id == patient_user_id
        )
        .first()
    )

    if not patient:
        raise HTTPException(
            status_code=404,
            detail="Patient not found"
        )

    files = (
        db.query(FileRecord)
        .filter(
            FileRecord.patient_id == patient.id
        )
        .all()
    )

    return files