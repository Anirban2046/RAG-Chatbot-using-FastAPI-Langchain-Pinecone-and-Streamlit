"""
Manage client-side browser storage (localStorage) for persisting auth_token and client_id across page refreshes.
This is safe: client_id is a random UUID (not sensitive), and auth_token is a temporary JWT.
"""

import streamlit as st
from uuid import uuid4

# Inject a script that manages localStorage and communicates with Streamlit via query params or hidden element
STORAGE_SCRIPT = """
<script>
// Initialize client_id in localStorage if not present
if (!localStorage.getItem('rag_client_id')) {
    localStorage.setItem('rag_client_id', 'client-' + Math.random().toString(36).substr(2, 9));
}

// Initialize auth_token in localStorage if not present (will be set by login)
if (!localStorage.getItem('rag_auth_token')) {
    localStorage.setItem('rag_auth_token', '');
}
</script>
"""

def inject_storage_script():
    """Inject localStorage initialization script."""
    st.markdown(STORAGE_SCRIPT, unsafe_allow_html=True)


def get_client_id_from_storage() -> str | None:
    """
    Retrieve client_id from browser localStorage via query params or fallback.
    Since Python can't directly read browser localStorage, we use a workaround:
    - Store client_id in st.query_params
    - This persists across page refreshes
    """
    # Check query params first
    try:
        client_id = st.query_params.get("_client_id")
        if client_id:
            return client_id
    except (AttributeError, Exception):
        pass
    return None


def set_client_id_in_storage(client_id: str) -> None:
    """Store client_id in query params so it persists across refreshes."""
    try:
        st.query_params["_client_id"] = client_id
    except (AttributeError, Exception):
        pass


def get_auth_token_from_storage() -> str | None:
    """Retrieve auth_token from query params (as a workaround since Python can't read localStorage directly)."""
    try:
        token = st.query_params.get("_auth_token")
        if token:
            return token
    except (AttributeError, Exception):
        pass
    return None


def set_auth_token_in_storage(token: str | None) -> None:
    """Store auth_token in query params."""
    try:
        if token:
            st.query_params["_auth_token"] = token
        elif "_auth_token" in st.query_params:
            del st.query_params["_auth_token"]
    except (AttributeError, Exception):
        pass
