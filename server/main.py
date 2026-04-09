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



app=FastAPI(title="RAG Chatbot API",description="API for RAG Chatbot")


@app.on_event("startup")
def init_db():
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database schema initialized")
    except Exception:
        logger.exception("Database initialization failed. Check DATABASE_URL and PostgreSQL server status.")

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