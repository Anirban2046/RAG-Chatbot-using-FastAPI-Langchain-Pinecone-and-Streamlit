from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import relationship

from db import Base


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    role = Column(String(20), nullable=False)
    content = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user = relationship("User", back_populates="chat_messages")


class UploadedDocument(Base):
    __tablename__ = "uploaded_documents"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    original_filename = Column(String(255), nullable=False)
    stored_filename = Column(String(255), nullable=False)
    namespace = Column(String(128), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user = relationship("User", back_populates="uploaded_documents")


class AnonymousSession(Base):
    __tablename__ = "anonymous_sessions"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(String(64), unique=True, index=True, nullable=False)
    namespace = Column(String(128), unique=True, index=True, nullable=False)
    messages_json = Column(Text, nullable=False, default="[]")
    uploaded_docs_json = Column(Text, nullable=False, default="[]")
    is_closed = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    last_active_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
