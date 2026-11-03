from fastapi import APIRouter
from fastapi import Depends

from sqlalchemy.orm import Session

from app.schemas.auth import (
    ChangePasswordRequest,
    DoctorRegisterRequest,
    CurrentUserResponse,
    LoginRequest,
)
from app.core.dependencies import get_db
from app.models.user import User
from app.core.security import get_current_user, require_admin
from app.schemas.auth import EmailRequest, ResetPasswordRequest, TokenRequest
from app.modules.auth import tokens

from app.modules.auth.service import (
    change_password_service,
    register_doctor_service,
    login_service
)

router = APIRouter()


@router.post("/login")
def login(
    payload: LoginRequest,
    db: Session = Depends(get_db)
):
    return login_service(
        email=payload.email,
        password=payload.password,
        db=db
    )


@router.get(
    "/me",
    response_model=CurrentUserResponse,
)
def get_my_identity(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # The token only carries identity. The profile fields live on the row,
    # so they are read here rather than widening the shared dependency.
    user = (
        db.query(User)
        .filter(User.id == current_user["user_id"])
        .first()
    )
    return {
        **current_user,
        "full_name": user.full_name if user else None,
        "phone": user.phone if user else None,
        "email": user.email if user else None,
        "is_verified": bool(user and user.is_verified),
    }


@router.post("/register-doctor")
def register_doctor(
    payload: DoctorRegisterRequest,
    db: Session = Depends(get_db)
):
    return register_doctor_service(payload, db)


@router.post("/change-password")
def change_password(
    payload: ChangePasswordRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return change_password_service(
        user_id=current_user["user_id"],
        current_password=payload.current_password,
        new_password=payload.new_password,
        db=db
    )


@router.post("/forgot-password")
def forgot_password(payload: EmailRequest, db: Session = Depends(get_db)):
    return tokens.request_link(str(payload.email), "reset", db)


@router.post("/reset-password")
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)):
    return tokens.reset_password(payload.token, payload.new_password, db)


@router.post("/request-email-verification")
def request_verification(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    user = db.get(User, current_user["user_id"])
    return tokens.request_link(user.email, "verify", db)


@router.post("/verify-email")
def verify_email(payload: TokenRequest, db: Session = Depends(get_db)):
    user = tokens.consume(payload.token, "verify", db)
    user.is_verified = True
    db.commit()
    return {"message": "Email verified."}


@router.post("/refresh")
def refresh_session(payload: TokenRequest, db: Session = Depends(get_db)):
    user = tokens.consume(payload.token, "refresh", db)
    return tokens.session_tokens(user, db)


@router.post("/logout")
def logout(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    from sqlalchemy import update
    db.execute(update(User).where(User.id == current_user["user_id"])
               .values(token_version=User.token_version + 1))
    db.commit()
    return {"message": "All sessions revoked."}


@router.get("/demo-outbox")
def demo_outbox(current_user=Depends(require_admin)):
    from fastapi import HTTPException
    if tokens.email_mode() != "demo":
        raise HTTPException(status_code=404, detail="Demo email is disabled")
    return {"mode": "demo", "messages": [item for item in tokens._DEMO_OUTBOX
                                           if item["expires_at"] > tokens._now()]}
