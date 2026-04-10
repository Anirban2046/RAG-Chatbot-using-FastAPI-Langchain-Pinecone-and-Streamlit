import json
import time
from uuid import uuid4
from utils.api import get_anonymous_session_state, save_anonymous_session_state
from utils.browser_storage import (
    get_client_id_from_storage, set_client_id_in_storage,
    get_auth_token_from_storage, set_auth_token_in_storage,
    get_auth_disabled_from_storage, set_auth_disabled_in_storage,
)


def _generate_client_id() -> str:
    return uuid4().hex


def _snapshot_signature(messages: list, uploaded_docs: list) -> str:
    payload = {
        "messages": messages,
        "uploaded_docs": uploaded_docs,
    }
    return json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True)


def save_state(state):
    # Intentionally no-op in deployed Streamlit environments.
    # Writing shared server-side files leaks one visitor's state to others.
    return None


def sync_session_from_disk(session_state):
    session_state.setdefault("_anonymous_hydrated_client_id", None)
    session_state.setdefault("_last_anonymous_persist_signature", None)
    session_state.setdefault("_anonymous_hydration_ready", False)
    session_state.setdefault("_ignore_auth_cookie_until", 0.0)

    # Initialize fallback storage keys for browser compatibility (localStorage/sessionStorage)
    session_state.setdefault("_browser_storage_client_id", None)
    session_state.setdefault("_browser_storage_auth_token", None)
    session_state.setdefault("_browser_storage_auth_disabled", None)

    # Restore client identity from cookie and hydrate state from backend DB.
    # For browser compatibility (especially Firefox), always re-persist the client_id cookie.
    stored_client_id = get_client_id_from_storage()
    if stored_client_id:
        session_state["client_id"] = stored_client_id
    elif "client_id" not in session_state:
        new_client_id = _generate_client_id()
        session_state["client_id"] = new_client_id
    # Always re-persist the client_id cookie with full expiration to handle browser cache issues
    if "client_id" in session_state:
        set_client_id_in_storage(session_state["client_id"])

    # Auth token is restored from cookie storage unless a short-term logout suppression window is active.
    ignore_cookie_until = float(session_state.get("_ignore_auth_cookie_until", 0.0) or 0.0)
    suppress_auth_cookie = time.time() < ignore_cookie_until
    auth_disabled = bool(get_auth_disabled_from_storage())
    stored_token = None if suppress_auth_cookie or auth_disabled else get_auth_token_from_storage()
    if suppress_auth_cookie or auth_disabled:
        set_auth_token_in_storage(None)
    if stored_token:
        session_state["auth_token"] = stored_token
    else:
        session_state.setdefault("auth_token", None)
    
    session_state.setdefault("auth_username", None)
    
    # Anonymous messages/docs are restored from backend DB.
    # Authenticated messages/docs are fetched from the backend during _hydrate_authenticated_state().
    is_anonymous = not session_state.get("auth_token")
    if is_anonymous:
        client_id = session_state.get("client_id")
        # Validate client_id is a proper string before using it
        if client_id and isinstance(client_id, str) and client_id.strip():
            should_hydrate = session_state.get("_anonymous_hydrated_client_id") != client_id
            if should_hydrate:
                response = get_anonymous_session_state(client_id)
                if response.status_code == 200:
                    try:
                        payload = response.json()
                    except Exception:
                        payload = {}
                    session_state["messages"] = payload.get("messages", [])
                    session_state["uploaded_docs"] = payload.get("uploaded_docs", [])
                    session_state["_anonymous_hydration_ready"] = True
                else:
                    session_state.setdefault("messages", [])
                    session_state.setdefault("uploaded_docs", [])
                    session_state["_anonymous_hydration_ready"] = False

                session_state["_anonymous_hydrated_client_id"] = client_id
                session_state["_last_anonymous_persist_signature"] = _snapshot_signature(
                    session_state.get("messages", []),
                    session_state.get("uploaded_docs", []),
                )
            else:
                session_state.setdefault("messages", [])
                session_state.setdefault("uploaded_docs", [])
                session_state["_anonymous_hydration_ready"] = True
        else:
            session_state.setdefault("messages", [])
            session_state.setdefault("uploaded_docs", [])
            session_state["_anonymous_hydrated_client_id"] = None
            session_state["_last_anonymous_persist_signature"] = None
            session_state["_anonymous_hydration_ready"] = False
    else:
        session_state.setdefault("messages", [])
        session_state.setdefault("uploaded_docs", [])
        session_state["_anonymous_hydrated_client_id"] = None
        session_state["_anonymous_hydration_ready"] = False


def persist_session(session_state):
    # For anonymous users, persist messages and uploaded_docs to backend DB so they survive hard refreshes.
    # For authenticated users, these are saved to the backend by API calls.
    is_anonymous = not session_state.get("auth_token")
    if is_anonymous:
        client_id = session_state.get("client_id")
        messages = session_state.get("messages", [])
        uploaded_docs = session_state.get("uploaded_docs", [])
        if client_id and session_state.get("_anonymous_hydration_ready"):
            signature = _snapshot_signature(messages, uploaded_docs)
            if signature != session_state.get("_last_anonymous_persist_signature"):
                response = save_anonymous_session_state(client_id, messages, uploaded_docs)
                if response.status_code == 200:
                    session_state["_last_anonymous_persist_signature"] = signature
    save_state(session_state)


def clear_chat_state(session_state):
    session_state["messages"] = []
    session_state["uploaded_docs"] = []
    session_state["hide_welcome"] = False
    persist_session(session_state)
    save_state(session_state)


def clear_all_state(session_state):
    session_state["auth_token"] = None
    session_state["auth_username"] = None
    session_state["messages"] = []
    session_state["uploaded_docs"] = []
    session_state["hide_welcome"] = False
    session_state["current_profile"] = None
    session_state["profile_dialog_open"] = False
    session_state["edit_profile_dialog_open"] = False
    session_state["_anonymous_hydrated_client_id"] = None
    session_state["_last_anonymous_persist_signature"] = None
    session_state["_anonymous_hydration_ready"] = False
    session_state["_hydrated_auth_token"] = None
    set_auth_token_in_storage(None)
    set_auth_disabled_in_storage(True)
    save_state(session_state)


def logout_and_reset_state(session_state):
    # Clear any anonymous session data tied to the current browser identity.
    old_client_id = session_state.get("client_id")
    if old_client_id:
        try:
            save_anonymous_session_state(old_client_id, [], [])
        except Exception:
            pass

    clear_all_state(session_state)
    new_client_id = _generate_client_id()
    session_state["client_id"] = new_client_id
    set_client_id_in_storage(new_client_id)

    # Ignore stale auth cookie for a few seconds while browser-side cookie removal settles.
    session_state["_ignore_auth_cookie_until"] = time.time() + 5.0


def clear_auth_disabled_state(session_state):
    set_auth_disabled_in_storage(False)
    session_state["_ignore_auth_cookie_until"] = 0.0
