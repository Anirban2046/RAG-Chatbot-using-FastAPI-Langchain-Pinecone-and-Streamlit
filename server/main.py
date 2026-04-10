from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import threading

from config import ANON_CLEANUP_INTERVAL_SECONDS, CORS_ALLOW_ORIGINS
from db import Base, engine
from logger import logger
from middlewares.exception_handlers import catch_exception_middleware
from modules.anonymous_session_store import cleanup_inactive_sessions
from models.content import AnonymousSession, ChatMessage, UploadedDocument  # noqa: F401
from models.user import User  # noqa: F401
from db import SessionLocal
from routes.ask_question import router as ask_router
from routes.auth import router as auth_router
from routes.session_state import router as session_router
from routes.upload_pdfs import router as upload_router
from sqlalchemy import inspect, text



app=FastAPI(title="RAG Chatbot API",description="API for RAG Chatbot")
_cleanup_stop_event = threading.Event()
_cleanup_thread: threading.Thread | None = None


def _run_anonymous_cleanup_worker():
    while not _cleanup_stop_event.is_set():
        try:
            with SessionLocal() as db:
                deleted = cleanup_inactive_sessions(db)
            if deleted:
                logger.info("Background anonymous session cleanup removed %s stale session(s)", deleted)
        except Exception:
            logger.exception("Background anonymous namespace cleanup failed")

        if _cleanup_stop_event.wait(timeout=ANON_CLEANUP_INTERVAL_SECONDS):
            break


@app.on_event("startup")
def init_db():
    global _cleanup_thread
    try:
        Base.metadata.create_all(bind=engine)
        _ensure_user_profile_columns()
        _ensure_anonymous_sessions_table_schema()
        logger.info("Database schema initialized")

        if _cleanup_thread is None or not _cleanup_thread.is_alive():
            _cleanup_stop_event.clear()
            _cleanup_thread = threading.Thread(
                target=_run_anonymous_cleanup_worker,
                name="anon-namespace-cleanup-worker",
                daemon=True,
            )
            _cleanup_thread.start()
            logger.info("Background anonymous cleanup worker started")
    except Exception:
        logger.exception("Database initialization failed. Check DATABASE_URL and PostgreSQL server status.")


@app.on_event("shutdown")
def shutdown_background_workers():
    global _cleanup_thread
    _cleanup_stop_event.set()
    if _cleanup_thread and _cleanup_thread.is_alive():
        _cleanup_thread.join(timeout=2)
    _cleanup_thread = None


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


def _ensure_anonymous_sessions_table_schema():
    inspector = inspect(engine)
    if "anonymous_sessions" not in inspector.get_table_names():
        return

    existing_columns = {column["name"] for column in inspector.get_columns("anonymous_sessions")}
    required_columns = {
        "id",
        "client_id",
        "namespace",
        "messages_json",
        "uploaded_docs_json",
        "is_closed",
        "created_at",
        "updated_at",
        "last_active_at",
    }
    if required_columns.issubset(existing_columns):
        return

    if engine.dialect.name != "sqlite":
        logger.warning(
            "anonymous_sessions table has legacy schema (%s) and requires manual migration for %s",
            sorted(existing_columns),
            engine.dialect.name,
        )
        return

    logger.warning(
        "Legacy anonymous_sessions schema detected (columns=%s). Rebuilding table for compatibility.",
        sorted(existing_columns),
    )
    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE anonymous_sessions RENAME TO anonymous_sessions_legacy"))
        connection.execute(
            text(
                """
                CREATE TABLE anonymous_sessions (
                    id INTEGER NOT NULL PRIMARY KEY,
                    client_id VARCHAR(64) NOT NULL,
                    namespace VARCHAR(128) NOT NULL,
                    messages_json TEXT NOT NULL DEFAULT '[]',
                    uploaded_docs_json TEXT NOT NULL DEFAULT '[]',
                    is_closed BOOLEAN NOT NULL DEFAULT 0,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    last_active_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        )
        connection.execute(text("CREATE UNIQUE INDEX ix_anonymous_sessions_client_id ON anonymous_sessions (client_id)"))
        connection.execute(text("CREATE UNIQUE INDEX ix_anonymous_sessions_namespace ON anonymous_sessions (namespace)"))
        connection.execute(text("CREATE INDEX ix_anonymous_sessions_id ON anonymous_sessions (id)"))

        legacy_columns = {
            row[1] for row in connection.execute(text("PRAGMA table_info('anonymous_sessions_legacy')")).fetchall()
        }
        if {"client_id", "namespace"}.issubset(legacy_columns):
            connection.execute(
                text(
                    """
                    INSERT INTO anonymous_sessions (client_id, namespace, messages_json, uploaded_docs_json, is_closed, last_active_at)
                    SELECT
                        client_id,
                        namespace,
                        COALESCE(messages_json, '[]'),
                        COALESCE(uploaded_docs_json, '[]'),
                        COALESCE(is_closed, 0),
                        COALESCE(last_active_at, CURRENT_TIMESTAMP)
                    FROM anonymous_sessions_legacy
                    """
                )
            )

        connection.execute(text("DROP TABLE anonymous_sessions_legacy"))

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