from fastapi import FastAPI

from app.core.database import engine
from app.models.base import Base

from app.modules.users.routes import router as user_router
from app.modules.auth.routes import router as auth_router

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="SasthoSetu API",
    version="1.0.0"
)

app.include_router(
    user_router,
    prefix="/api/v1",
    tags=["Users"]
)

app.include_router(
    auth_router,
    prefix="/api/v1/auth",
    tags=["Authentication"]
)

@app.get("/")
def root():
    return {
        "message": "SasthoSetu API Running"
    }


@app.get("/health")
def health_check():
    return {
        "status": "healthy"
    }