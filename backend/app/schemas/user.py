from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    full_name: str
    email: EmailStr
    phone: str
    password: str


class UserUpdateRequest(BaseModel):
    """What an account holder may change about their own profile.

    Email is deliberately absent: it is the login name and the recovery
    channel, so a silent swap would hand an account to whoever can make a
    single authenticated request. Role is absent for the same reason with
    higher stakes.
    """
    full_name: str | None = Field(default=None, min_length=2, max_length=100)
    phone: str | None = Field(
        default=None,
        pattern=r"^01[3-9]\d{8}$",
    )
