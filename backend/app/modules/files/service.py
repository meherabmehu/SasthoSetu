import os

from fastapi import UploadFile
from fastapi import HTTPException

from sqlalchemy.orm import Session

from app.models.patient import Patient
from app.models.file_record import FileRecord
from fastapi.responses import FileResponse, Response

# Uploads are held in the database rather than on disk. These are medical
# records, and a local directory is lost whenever the instance is replaced -
# which on a serverless host is after every request, and on any host with
# more than one instance means the file is only present on the machine that
# received it.
#
# Rows created before that change still point at this directory, so it stays
# readable for them. Nothing new is written here.
UPLOAD_DIR = "uploads"

# Scans and reports; large enough for a chest film, small enough that a
# single request cannot exhaust the database connection's memory.
MAX_UPLOAD_BYTES = 10 * 1024 * 1024

ALLOWED_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "application/pdf",
}


def _safe_name(name: str | None) -> str:
    """Reduce a client-supplied filename to something safe to store.

    The name is echoed back in the download's Content-Disposition header, so
    it must not carry path separators or control characters.
    """
    candidate = os.path.basename(name or "").strip()
    candidate = candidate.replace("\\", "").replace("\r", "").replace("\n", "")
    if not candidate or candidate in {".", ".."}:
        return "upload"
    return candidate[:120]


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

    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=415,
            detail=(
                "Only JPEG, PNG, WebP images and PDF documents can be "
                "uploaded"
            )
        )

    payload = file.file.read(MAX_UPLOAD_BYTES + 1)

    if not payload:
        raise HTTPException(
            status_code=400,
            detail="The uploaded file is empty"
        )

    if len(payload) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=(
                f"Files must be {MAX_UPLOAD_BYTES // (1024 * 1024)} MB "
                "or smaller"
            )
        )

    record = FileRecord(
        patient_id=patient.id,
        uploaded_by=patient_user_id,
        file_name=_safe_name(file.filename),
        file_path=None,
        content=payload,
        file_size=len(payload),
        file_type=file.content_type
    )

    db.add(record)
    db.commit()

    return {
        "message": "File uploaded successfully",
        "file_name": record.file_name
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

    if file.content is not None:
        return Response(
            content=file.content,
            media_type=file.file_type,
            headers={
                "Content-Disposition":
                    f'attachment; filename="{file.file_name}"'
            }
        )

    # Uploaded before file contents were stored in the database.
    if not file.file_path or not os.path.exists(file.file_path):
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

    if file.file_path and os.path.exists(file.file_path):
        os.remove(file.file_path)

    db.delete(file)
    db.commit()

    return {
        "message": "File deleted successfully"
    }
