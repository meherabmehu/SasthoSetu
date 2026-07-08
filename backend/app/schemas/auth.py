from pydantic import BaseModel


class LoginRequest(BaseModel):
    email: str
    password: str


class CurrentUserResponse(BaseModel):
    user_id: str
    role: str
