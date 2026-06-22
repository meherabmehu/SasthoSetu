from fastapi import APIRouter
from fastapi import Depends

from sqlalchemy.orm import Session

from app.core.dependencies import get_db

from app.modules.admin.service import (
    get_all_users_service,
    get_user_by_id_service,
    disable_user_service,
    enable_user_service,
    delete_user_service
)

router = APIRouter()


@router.get("/admin/users")
def get_all_users(
    db: Session = Depends(get_db)
):
    return get_all_users_service(
        db=db
    )


@router.get(
    "/admin/users/{user_id}"
)
def get_user_by_id(
    user_id: str,
    db: Session = Depends(get_db)
):
    return get_user_by_id_service(
        user_id=user_id,
        db=db
    )


@router.patch(
    "/admin/users/{user_id}/disable"
)
def disable_user(
    user_id: str,
    db: Session = Depends(get_db)
):
    return disable_user_service(
        user_id=user_id,
        db=db
    )


@router.patch(
    "/admin/users/{user_id}/enable"
)
def enable_user(
    user_id: str,
    db: Session = Depends(get_db)
):
    return enable_user_service(
        user_id=user_id,
        db=db
    )


@router.delete(
    "/admin/users/{user_id}"
)
def delete_user(
    user_id: str,
    db: Session = Depends(get_db)
):
    return delete_user_service(
        user_id=user_id,
        db=db
    )