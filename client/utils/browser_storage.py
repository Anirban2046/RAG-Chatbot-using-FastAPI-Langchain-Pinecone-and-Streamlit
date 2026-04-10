"""
Helpers for state persistence hooks.

Design:
- Keep auth token, chat messages, and uploaded docs only in process memory.
- Use client id as the stable browser key source.
- Mirror client id to a query param and a cookie to survive early refresh timing.

Result:
- Data survives browser refresh for the same browser URL/session.
- Data is dropped on app restart.
- Sensitive payloads (auth token/messages/docs) are not written to URLs.
"""

import json
import streamlit as st

# Keep a tiny bootstrap script for compatibility with existing layout/init flow.
STORAGE_SCRIPT = """
<script>
// Intentionally minimal. State persistence is handled by Python storage hooks.
</script>
"""

_BROWSER_SESSION_STATE: dict[str, dict] = {}
CLIENT_ID_COOKIE_NAME = "ragchat_client_id"
CLIENT_ID_QUERY_PARAM = "_client_id"


def _set_cookie_script(cookie_name: str, cookie_value: str | None) -> str:
    return f"""
    <script>
    (function() {{
        const cookieName = {cookie_name!r};
        const cookieValue = {cookie_value or ""!r};
        const maxAge = cookieValue ? 60 * 60 * 24 * 30 : 0;
        const expires = cookieValue ? `; Max-Age=${{maxAge}}` : '; Max-Age=0';
        const secure = window.location.protocol === 'https:' ? '; Secure' : '';
        const target = window.parent && window.parent.document ? window.parent.document : document;
        target.cookie = `${{cookieName}}=${{encodeURIComponent(cookieValue)}}; Path=/; SameSite=Lax${{expires}}${{secure}}`;
    }})();
    </script>
    """


def _write_browser_cookie(cookie_name: str, cookie_value: str | None) -> None:
    st.html(_set_cookie_script(cookie_name, cookie_value), width="stretch", unsafe_allow_javascript=True)


def _browser_scope_key() -> str | None:
    """Read the explicit client-id cookie if available."""
    try:
        cookies = dict(st.context.cookies)
    except Exception:
        return None

    client_id = cookies.get(CLIENT_ID_COOKIE_NAME)
    if isinstance(client_id, str) and client_id.strip():
        return client_id.strip()
    return None


def _query_param_client_id() -> str | None:
    try:
        value = st.query_params.get(CLIENT_ID_QUERY_PARAM)
    except Exception:
        value = None

    if isinstance(value, list):
        value = value[0] if value else None

    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _bucket_key() -> str | None:
    """Resolve the in-memory bucket key, preferring cookie client id, then query param client id."""
    browser_key = _browser_scope_key()
    if browser_key:
        return f"cookie:{browser_key}"

    query_client_id = _query_param_client_id()
    if query_client_id:
        return f"client:{query_client_id}"

    return None


def _get_bucket(create: bool = False) -> dict | None:
    key = _bucket_key()
    if not key:
        return None

    if key not in _BROWSER_SESSION_STATE:
        if not create:
            return None
        _BROWSER_SESSION_STATE[key] = {}
    return _BROWSER_SESSION_STATE[key]


def inject_storage_script():
    """Inject compatibility bootstrap markup (no state is stored in localStorage)."""
    st.markdown(STORAGE_SCRIPT, unsafe_allow_html=True)


def get_client_id_from_storage() -> str | None:
    """Read client id from query param, then cookie, then in-memory fallback bucket."""
    value = _query_param_client_id()
    if value:
        return value

    try:
        value = st.context.cookies.get(CLIENT_ID_COOKIE_NAME)
    except Exception:
        value = None
    if isinstance(value, str) and value.strip():
        return value.strip()

    bucket = _get_bucket(create=False)
    if not bucket:
        return None
    value = bucket.get("client_id")
    return value if isinstance(value, str) and value else None


def set_client_id_in_storage(client_id: str) -> None:
    """Persist client id in query params, cookie, and current in-memory bucket."""
    if client_id:
        st.query_params[CLIENT_ID_QUERY_PARAM] = client_id
    _write_browser_cookie(CLIENT_ID_COOKIE_NAME, client_id)
    bucket = _get_bucket(create=True)
    if bucket is not None and client_id:
        bucket["client_id"] = client_id


def get_auth_token_from_storage() -> str | None:
    """Read auth token from the in-memory bucket only."""
    bucket = _get_bucket(create=False)
    if not bucket:
        return None
    token = bucket.get("auth_token")
    return token if isinstance(token, str) and token else None


def set_auth_token_in_storage(token: str | None) -> None:
    """Write auth token to the in-memory bucket only."""
    bucket = _get_bucket(create=True)
    if bucket is None:
        return None
    if token:
        bucket["auth_token"] = token
    else:
        bucket.pop("auth_token", None)


def get_messages_from_storage() -> list | None:
    """Read anonymous chat messages from the in-memory bucket."""
    bucket = _get_bucket(create=False)
    if not bucket:
        return None
    messages = bucket.get("messages")
    if not isinstance(messages, list):
        return None
    return json.loads(json.dumps(messages, ensure_ascii=True))


def set_messages_in_storage(messages: list) -> None:
    """Write anonymous chat messages to the in-memory bucket."""
    bucket = _get_bucket(create=True)
    if bucket is not None:
        bucket["messages"] = json.loads(json.dumps(messages, ensure_ascii=True))


def get_uploaded_docs_from_storage() -> list | None:
    """Read anonymous uploaded-doc metadata from the in-memory bucket."""
    bucket = _get_bucket(create=False)
    if not bucket:
        return None
    docs = bucket.get("uploaded_docs")
    if not isinstance(docs, list):
        return None
    return json.loads(json.dumps(docs, ensure_ascii=True))


def set_uploaded_docs_in_storage(docs: list) -> None:
    """Write anonymous uploaded-doc metadata to the in-memory bucket."""
    bucket = _get_bucket(create=True)
    if bucket is not None:
        bucket["uploaded_docs"] = json.loads(json.dumps(docs, ensure_ascii=True))
