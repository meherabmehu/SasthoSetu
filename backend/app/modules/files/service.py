import os

from fastapi import UploadFile
from fastapi import HTTPException

from sqlalchemy.orm import Session

from app.models.patient import Patient
from app.models.file_record import FileRecord
from fastapi.responses import FileResponse

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
def _assert_file_access(file, current_user, db) -> None:
    """A file may be read by its patient, a clinician, or an administrator.

    The route only receives a file id, so ownership has to be resolved from
    the record itself; otherwise anyone holding an id could read a stranger's
    scan or report.
    """
    if current_user is None:
        return

    role = current_user.get("role")
    if role in ("DOCTOR", "ADMIN"):
        return

    patient = (
        db.query(Patient)
        .filter(Patient.id == file.patient_id)
        .first()
    )
    if not patient or patient.user_id != current_user.get("user_id"):
        raise HTTPException(
            status_code=403,
            detail="You cannot access another patient's file"
        )


def download_file_service(
    file_id: str,
    db: Session,
    current_user: dict | None = None
):

    file = (
        db.query(FileRecord)
        .filter(
            FileRecord.id == file_id
        )
        .first()
    )

    if not file:
        raise HTTPException(
            status_code=404,
            detail="File not found"
        )

    _assert_file_access(file, current_user, db)

    if not os.path.exists(file.file_path):
        raise HTTPException(
            status_code=404,
            detail="Physical file not found"
        )

    return FileResponse(
        path=file.file_path,
        filename=file.file_name,
        media_type=file.file_type
    )
def delete_file_service(
    file_id: str,
    db: Session,
    current_user: dict | None = None
):

    file = (
        db.query(FileRecord)
        .filter(
            FileRecord.id == file_id
        )
        .first()
    )

    if not file:
        raise HTTPException(
            status_code=404,
            detail="File not found"
        )

    _assert_file_access(file, current_user, db)

    if os.path.exists(file.file_path):
        os.remove(file.file_path)

    db.delete(file)
    db.commit()

    return {
        "message": "File deleted successfully"
    }