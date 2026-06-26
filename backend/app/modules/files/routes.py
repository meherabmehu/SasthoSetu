from fastapi import APIRouter
from fastapi import Depends
from fastapi import UploadFile
from fastapi import File

from sqlalchemy.orm import Session

from app.core.dependencies import get_db

from app.modules.files.service import (
    upload_file_service,
    get_patient_files_service
)

router = APIRouter()


@router.post(
    "/files/upload/{patient_user_id}"
)
def upload_file(
    patient_user_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    return upload_file_service(
        patient_user_id=patient_user_id,
        file=file,
        db=db
    )


@router.get(
    "/files/{patient_user_id}"
)
def get_patient_files(
    patient_user_id: str,
    db: Session = Depends(get_db)
):
    return get_patient_files_service(
        patient_user_id=patient_user_id,
        db=db
    )