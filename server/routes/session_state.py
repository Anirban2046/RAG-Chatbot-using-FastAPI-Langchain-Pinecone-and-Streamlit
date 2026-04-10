from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from db import get_db
from modules.anonymous_session_store import (
    close_session,
    get_session_state as get_anonymous_session_state,
    upsert_session_state,
)
from modules.auth import get_current_user
from modules.principal import sanitize_client_id
from modules.user_content_store import get_user_content_state
from models.user import User
from schemas.session_state import AnonymousClosePayload, AnonymousSessionStatePayload

router = APIRouter(prefix="/session", tags=["session"])


@router.get("/state")
def get_session_state(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return get_user_content_state(db, user)


@router.get("/anonymous/state")
def get_anonymous_state(
    db: Session = Depends(get_db),
    x_client_id: str | None = Header(default=None, alias="X-Client-Id"),
):
    client_id = sanitize_client_id(x_client_id)
    if client_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing or invalid X-Client-Id header",
        )
    return get_anonymous_session_state(db, client_id)


@router.post("/anonymous/state")
def set_anonymous_state(
    payload: AnonymousSessionStatePayload,
    db: Session = Depends(get_db),
    x_client_id: str | None = Header(default=None, alias="X-Client-Id"),
):
    client_id = sanitize_client_id(x_client_id)
    if client_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing or invalid X-Client-Id header",
        )
    return upsert_session_state(db, client_id, payload.messages, payload.uploaded_docs)


@router.post("/anonymous/close")
def close_anonymous_state(
    payload: AnonymousClosePayload | None = None,
    db: Session = Depends(get_db),
    x_client_id: str | None = Header(default=None, alias="X-Client-Id"),
):
    client_id = sanitize_client_id(x_client_id) or sanitize_client_id((payload or AnonymousClosePayload()).client_id)
    if client_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing or invalid X-Client-Id header",
        )
    close_session(db, client_id)
    return {"status": "closed"}
