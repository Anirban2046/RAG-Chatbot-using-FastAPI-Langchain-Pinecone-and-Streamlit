from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import CORS_ALLOW_ORIGINS
from db import Base, engine
from logger import logger
from middlewares.exception_handlers import catch_exception_middleware
from models.content import ChatMessage, UploadedDocument  # noqa: F401
from models.user import User  # noqa: F401
from routes.ask_question import router as ask_router
from routes.auth import router as auth_router
from routes.session_state import router as session_router
from routes.upload_pdfs import router as upload_router
from sqlalchemy import inspect, text



app=FastAPI(title="RAG Chatbot API",description="API for RAG Chatbot")


@app.on_event("startup")
def init_db():
    try:
        Base.metadata.create_all(bind=engine)
        _ensure_user_profile_columns()
        logger.info("Database schema initialized")
    except Exception:
        logger.exception("Database initialization failed. Check DATABASE_URL and PostgreSQL server status.")


def _ensure_user_profile_columns():
    inspector = inspect(engine)
    existing_columns = {column["name"] for column in inspector.get_columns("users")}
    required_columns = {
        "full_name": "ALTER TABLE users ADD COLUMN full_name VARCHAR(120)",
        "profile_photo_filename": "ALTER TABLE users ADD COLUMN profile_photo_filename VARCHAR(255)",
        "profile_photo_mime": "ALTER TABLE users ADD COLUMN profile_photo_mime VARCHAR(100)",
    }

    with engine.begin() as connection:
        for column_name, ddl in required_columns.items():
            if column_name not in existing_columns:
                connection.execute(text(ddl))

# CORS Setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOW_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Client-Id"],
)



# middleware exception handlers
app.middleware("http")(catch_exception_middleware)

app.include_router(auth_router)
app.include_router(upload_router)
app.include_router(ask_router)
app.include_router(session_router)