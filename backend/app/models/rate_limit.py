from sqlalchemy import BigInteger, Column, Integer, String

from app.models.base import Base


class RateLimitWindow(Base):
    __tablename__ = "rate_limit_windows"
    client_hash = Column(String(64), primary_key=True)
    window_start = Column(BigInteger, primary_key=True)
    requests = Column(Integer, nullable=False)
