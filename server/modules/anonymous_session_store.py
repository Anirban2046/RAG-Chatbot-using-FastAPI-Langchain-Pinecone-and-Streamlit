import json
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from config import ANON_NAMESPACE_TTL_HOURS
from models.content import AnonymousSession
from modules.load_vectorstore import clear_vectorstore


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_messages(messages) -> list[dict[str, str]]:
    if not isinstance(messages, list):
        return []

    normalized: list[dict[str, str]] = []
    for item in messages:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role", "assistant"))
        content = str(item.get("content", ""))
        normalized.append({"role": role, "content": content})
    return normalized


def _normalize_uploaded_docs(uploaded_docs) -> list[str]:
    if not isinstance(uploaded_docs, list):
        return []
    return [str(name) for name in uploaded_docs if isinstance(name, str)]


def _safe_load_json_list(payload: str) -> list:
    try:
        value = json.loads(payload)
    except (json.JSONDecodeError, TypeError):
        return []
    return value if isinstance(value, list) else []


def _get_or_create_session(db: Session, client_id: str) -> AnonymousSession:
    namespace = f"anon-{client_id}"
    existing = db.query(AnonymousSession).filter(AnonymousSession.client_id == client_id).first()
    if existing:
        return existing

    record = AnonymousSession(client_id=client_id, namespace=namespace)
    db.add(record)
    db.flush()
    return record


def touch_session(db: Session, client_id: str) -> AnonymousSession:
    record = _get_or_create_session(db, client_id)
    record.last_active_at = _now_utc()
    if record.is_closed:
        record.is_closed = False
    db.commit()
    db.refresh(record)
    return record


def get_session_state(db: Session, client_id: str) -> dict:
    record = touch_session(db, client_id)
    messages = _safe_load_json_list(record.messages_json)
    uploaded_docs = _safe_load_json_list(record.uploaded_docs_json)
    return {
        "messages": _normalize_messages(messages),
        "uploaded_docs": _normalize_uploaded_docs(uploaded_docs),
    }


def upsert_session_state(db: Session, client_id: str, messages, uploaded_docs) -> dict:
    record = _get_or_create_session(db, client_id)
    safe_messages = _normalize_messages(messages)
    safe_docs = _normalize_uploaded_docs(uploaded_docs)

    record.messages_json = json.dumps(safe_messages, ensure_ascii=True)
    record.uploaded_docs_json = json.dumps(safe_docs, ensure_ascii=True)
    record.last_active_at = _now_utc()
    record.is_closed = False

    db.commit()
    db.refresh(record)

    return {
        "messages": safe_messages,
        "uploaded_docs": safe_docs,
    }


def clear_session_state(db: Session, client_id: str) -> None:
    record = _get_or_create_session(db, client_id)
    record.messages_json = "[]"
    record.uploaded_docs_json = "[]"
    record.last_active_at = _now_utc()
    record.is_closed = False
    db.commit()


def append_chat_turn(db: Session, client_id: str, user_question: str, assistant_answer: str) -> None:
    record = _get_or_create_session(db, client_id)
    existing_messages = _safe_load_json_list(record.messages_json)
    normalized_messages = _normalize_messages(existing_messages)
    normalized_messages.extend(
        [
            {"role": "user", "content": str(user_question)},
            {"role": "assistant", "content": str(assistant_answer)},
        ]
    )
    record.messages_json = json.dumps(normalized_messages, ensure_ascii=True)
    record.last_active_at = _now_utc()
    record.is_closed = False
    db.commit()


def set_uploaded_docs(db: Session, client_id: str, uploaded_docs) -> None:
    record = _get_or_create_session(db, client_id)
    safe_docs = _normalize_uploaded_docs(uploaded_docs)
    record.uploaded_docs_json = json.dumps(safe_docs, ensure_ascii=True)
    record.last_active_at = _now_utc()
    record.is_closed = False
    db.commit()


def close_session(db: Session, client_id: str) -> bool:
    record = _get_or_create_session(db, client_id)
    namespace = record.namespace

    record.messages_json = "[]"
    record.uploaded_docs_json = "[]"
    record.last_active_at = _now_utc()
    record.is_closed = True
    db.commit()

    clear_vectorstore(namespace=namespace)

    db.delete(record)
    db.commit()
    return True


def cleanup_inactive_sessions(db: Session) -> int:
    cutoff = _now_utc() - timedelta(hours=ANON_NAMESPACE_TTL_HOURS)
    stale_records = (
        db.query(AnonymousSession)
        .filter(AnonymousSession.last_active_at < cutoff)
        .all()
    )

    deleted = 0
    for record in stale_records:
        clear_vectorstore(namespace=record.namespace)
        db.delete(record)
        deleted += 1

    if deleted:
        db.commit()

    return deleted
