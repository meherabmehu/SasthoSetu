from fastapi import APIRouter
from fastapi import Depends
from fastapi import UploadFile
from fastapi import File

from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.core.security import get_current_user, require_self_or_clinician

from app.modules.files.service import (
    upload_file_service,
    get_patient_files_service,
    download_file_service,
    delete_file_service
)

router = APIRouter()


@router.post(
    "/files/upload/{patient_user_id}"
)
def upload_file(
    patient_user_id: str,
    file: UploadFile = File(...),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    require_self_or_clinician(patient_user_id, current_user)
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
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    require_self_or_clinician(patient_user_id, current_user)
    return get_patient_files_service(
        patient_user_id=patient_user_id,
        db=db
    )


@router.get(
    "/files/download/{file_id}"
)
def download_file(
    file_id: str,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return download_file_service(
        file_id=file_id,
        current_user=current_user,
        db=db
    )


@router.delete(
    "/files/{file_id}"
)
def delete_file(
    file_id: str,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return delete_file_service(
        file_id=file_id,
        current_user=current_user,
        db=db
    )