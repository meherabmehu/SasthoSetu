from pydantic import BaseModel
from pydantic import Field


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
