"""
Helpers for state persistence hooks.

Sensitive values (auth token, client id, messages, uploaded docs) must not be written to
URL query parameters because URLs are shareable and persisted in browser history.

Anonymous continuity requirement:
- Keep state across page refresh for the same browser session.
- Drop state on app restart.

Implementation note:
- We use server-memory buckets keyed by a browser cookie fingerprint.
- This avoids URL leakage and naturally clears when the Streamlit process restarts.
"""

import hashlib
import json
import streamlit as st

# Keep a tiny bootstrap script for compatibility with existing layout/init flow.
STORAGE_SCRIPT = """
<script>
// Intentionally left minimal. Sensitive session state is stored server-side session only.
</script>
"""

_BROWSER_SESSION_STATE: dict[str, dict] = {}


def _browser_scope_key() -> str | None:
    """Derive a stable browser-session key from current request cookies."""
    try:
        cookies = dict(st.context.cookies)
    except Exception:
        return None

    if not cookies:
        return None

    canonical = "|".join(f"{k}={cookies[k]}" for k in sorted(cookies.keys()))
    if not canonical:
        return None

    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _get_bucket(create: bool = False) -> dict | None:
    key = _browser_scope_key()
    if not key:
        return None

    if key not in _BROWSER_SESSION_STATE:
        if not create:
            return None
        _BROWSER_SESSION_STATE[key] = {}
    return _BROWSER_SESSION_STATE[key]

def inject_storage_script():
    """Inject localStorage initialization script."""
    st.markdown(STORAGE_SCRIPT, unsafe_allow_html=True)


def clear_legacy_query_params() -> None:
    """Remove old query-param keys that previously carried sensitive state."""
    try:
        for key in ("_client_id", "_auth_token", "_messages", "_uploaded_docs"):
            if key in st.query_params:
                del st.query_params[key]
    except Exception:
        pass


def get_client_id_from_storage() -> str | None:
    bucket = _get_bucket(create=False)
    if not bucket:
        return None
    value = bucket.get("client_id")
    return value if isinstance(value, str) and value else None


def set_client_id_in_storage(client_id: str) -> None:
    bucket = _get_bucket(create=True)
    if bucket is not None and client_id:
        bucket["client_id"] = client_id


def get_auth_token_from_storage() -> str | None:
    """Sensitive state is not persisted in URL or browser-readable storage."""
    return None


def set_auth_token_in_storage(token: str | None) -> None:
    """No-op by design to prevent URL leakage."""
    return None


def get_messages_from_storage() -> list | None:
    bucket = _get_bucket(create=False)
    if not bucket:
        return None
    messages = bucket.get("messages")
    if not isinstance(messages, list):
        return None
    return json.loads(json.dumps(messages, ensure_ascii=True))


def set_messages_in_storage(messages: list) -> None:
    bucket = _get_bucket(create=True)
    if bucket is not None:
        bucket["messages"] = json.loads(json.dumps(messages, ensure_ascii=True))


def get_uploaded_docs_from_storage() -> list | None:
    bucket = _get_bucket(create=False)
    if not bucket:
        return None
    docs = bucket.get("uploaded_docs")
    if not isinstance(docs, list):
        return None
    return json.loads(json.dumps(docs, ensure_ascii=True))


def set_uploaded_docs_in_storage(docs: list) -> None:
    bucket = _get_bucket(create=True)
    if bucket is not None:
        bucket["uploaded_docs"] = json.loads(json.dumps(docs, ensure_ascii=True))
