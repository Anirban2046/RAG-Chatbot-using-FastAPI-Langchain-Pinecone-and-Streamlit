import json
from pathlib import Path
from uuid import uuid4

STATE_FILE = Path(__file__).resolve().parents[1] / ".client_state.json"

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
    if not STATE_FILE.exists():
        return DEFAULT_STATE.copy()

    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return DEFAULT_STATE.copy()

    state = DEFAULT_STATE.copy()
    for key in state:
        if key in data:
            state[key] = data[key]
    return state


def save_state(state):
    payload = {
        "auth_token": state.get("auth_token"),
        "auth_username": state.get("auth_username"),
        "client_id": state.get("client_id"),
        "messages": state.get("messages", []),
        "uploaded_docs": state.get("uploaded_docs", []),
    }
    STATE_FILE.write_text(json.dumps(payload, ensure_ascii=True), encoding="utf-8")


def sync_session_from_disk(session_state):
    persisted = load_state()
    session_state.setdefault("auth_token", persisted.get("auth_token"))
    session_state.setdefault("auth_username", persisted.get("auth_username"))
    client_id = persisted.get("client_id") or _generate_client_id()
    session_state.setdefault("client_id", client_id)
    session_state["client_id"] = client_id
    session_state.setdefault("messages", persisted.get("messages", []))
    session_state.setdefault("uploaded_docs", persisted.get("uploaded_docs", []))


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
    save_state(session_state)
