import re

from models.user import User


def _sanitize_client_id(client_id: str | None) -> str | None:
    if not client_id:
        return None

    cleaned = re.sub(r"[^a-zA-Z0-9_-]", "", client_id.strip())
    if not cleaned:
        return None
    return cleaned[:64]


def sanitize_client_id(client_id: str | None) -> str | None:
    return _sanitize_client_id(client_id)


def resolve_namespace(user: User | None, client_id: str | None) -> str:
    if user is not None:
        return f"user-{user.id}"

    sanitized = _sanitize_client_id(client_id)
    if sanitized:
        return f"anon-{sanitized}"
    raise ValueError("Missing or invalid X-Client-Id for anonymous request")
