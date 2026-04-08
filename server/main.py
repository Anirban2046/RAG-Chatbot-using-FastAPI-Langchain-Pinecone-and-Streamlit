from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from middlewares.exception_handlers import catch_exception_middleware
from routes.upload_pdfs import router as upload_router
from routes.ask_question import router as ask_router
from routes.auth import router as auth_router
from db import Base, engine
from models.user import User  # noqa: F401
from logger import logger
from config import CORS_ALLOW_ORIGINS



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

# routers

# 0. auth
app.include_router(auth_router)

# 1. upload pdfs documents
app.include_router(upload_router)
# 2. asking query
app.include_router(ask_router)