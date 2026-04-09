from sqlalchemy import Column, Integer, String, DateTime, func
from sqlalchemy.orm import relationship

from db import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    chat_messages = relationship("ChatMessage", back_populates="user", cascade="all, delete-orphan")
    uploaded_documents = relationship("UploadedDocument", back_populates="user", cascade="all, delete-orphan")
