from fastapi import FastAPI

from app.core.database import engine
from app.models.base import Base

from app.modules.users.routes import router as user_router

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