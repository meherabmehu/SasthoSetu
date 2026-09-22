from pydantic import BaseModel, EmailStr, Field, constr


class LoginRequest(BaseModel):
    email: str
    password: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)


class CurrentUserResponse(BaseModel):
    user_id: str
    role: str
    # The profile fields the account page shows and edits. Optional so older
    # callers that only look at identity keep working if a row predates them.
    full_name: str | None = None
    phone: str | None = None


class DoctorRegisterRequest(BaseModel):
    """Self-service clinician sign-up.

    Creates the account and the doctor profile in one step. The profile is
    unverified: BMDC numbers are checked by an administrator, and until then
    the doctor is invisible to patients and cannot open consultations. That
    is the safety property the whole flow rests on, so nothing here may set
    verification_status.
    """
    full_name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    phone: str = Field(pattern=r"^01[3-9]\d{8}$")
    password: str = Field(min_length=8, max_length=128)
    bmdc_number: constr(min_length=4, max_length=50)
    specialization: str = Field(min_length=2, max_length=100)
    experience_years: int = Field(default=0, ge=0, le=70)
    consultation_fee: float = Field(default=500.0, gt=0)
    hospital_name: str = Field(min_length=2, max_length=200)
