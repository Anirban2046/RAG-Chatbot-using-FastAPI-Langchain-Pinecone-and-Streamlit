from uuid import uuid4
from utils.browser_storage import get_client_id_from_storage, set_client_id_in_storage, get_auth_token_from_storage, set_auth_token_in_storage

DEFAULT_STATE = {
    "auth_token": None,
    "auth_username": None,
    "client_id": None,
    "messages": [],
    "uploaded_docs": [],
}


def _generate_client_id() -> str:
    return uuid4().hex


def load_state():
    return DEFAULT_STATE.copy()


def save_state(state):
    # Intentionally no-op in deployed Streamlit environments.
    # Writing shared server-side files leaks one visitor's state to others.
    return None


def sync_session_from_disk(session_state):
    # Restore client_id from browser storage (query params as fallback to localStorage).
    # This persists the client_id across page refreshes, so anonymous users can access their uploads.
    stored_client_id = get_client_id_from_storage()
    if stored_client_id:
        session_state["client_id"] = stored_client_id
    elif "client_id" not in session_state:
        new_client_id = _generate_client_id()
        session_state["client_id"] = new_client_id
        set_client_id_in_storage(new_client_id)
    else:
        # Client ID already in session_state, ensure it's stored for next refresh
        set_client_id_in_storage(session_state["client_id"])
    
    # Restore auth_token from browser storage if present.
    stored_token = get_auth_token_from_storage()
    if stored_token:
        session_state["auth_token"] = stored_token
    else:
        session_state.setdefault("auth_token", None)
    
    session_state.setdefault("auth_username", None)
    session_state.setdefault("messages", [])
    session_state.setdefault("uploaded_docs", [])


def persist_session(session_state):
    save_state(session_state)


def clear_chat_state(session_state):
    session_state["messages"] = []
    session_state["uploaded_docs"] = []
    save_state(session_state)


def clear_content_state(session_state):
    session_state["messages"] = []
    session_state["uploaded_docs"] = []
    save_state(session_state)


def clear_all_state(session_state):
    session_state["auth_token"] = None
    session_state["auth_username"] = None
    session_state["messages"] = []
    session_state["uploaded_docs"] = []
    session_state["current_profile"] = None
    session_state["profile_dialog_open"] = False
    session_state["edit_profile_dialog_open"] = False
    set_auth_token_in_storage(None)  # Clear auth token from browser storage
    save_state(session_state)
