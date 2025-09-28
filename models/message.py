# models/message.py
from sqlalchemy import Column, Integer, String, DateTime, func
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True)
    artifact_id = Column(String, index=True)  # 🔹 유물 구분 (a 또는 b)
    role = Column(String)                     # "user" or "assistant"
    content = Column(String)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
