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
