import streamlit as st
from components.upload import render_uploader
from components.history_download import render_history_download
from components.chatUI import render_chat
from utils.api import clear_vectorstore_api, get_my_profile, get_session_state, login_user, register_user
from utils.state import clear_all_state, clear_chat_state, persist_session, sync_session_from_disk


st.set_page_config(page_title="AI RAG Chatbot", layout="wide")
st.title("RAG Chatbot")


def init_auth_state():
    sync_session_from_disk(st.session_state)
    st.session_state.setdefault("signin_form_version", 0)
    st.session_state.setdefault("register_form_version", 0)
    st.session_state.setdefault("anon_cleanup_done", False)

    if not st.session_state.anon_cleanup_done:
        _clear_anonymous_remote_vectorstore()
        st.session_state.anon_cleanup_done = True

    if st.session_state.get("auth_token"):
        _hydrate_authenticated_state()


def render_sidebar_auth_style():
    st.markdown(
        """
        <style>
        .auth-buttons {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 0.5rem;
            width: 100%;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _extract_error_message(response):
    """Extract user-friendly error message from API response."""
    try:
        data = response.json()
        detail = data.get("detail", "")
        # Extract user-friendly message from validation errors
        if isinstance(detail, list) and len(detail) > 0:
            return detail[0].get("msg", "Invalid request")
        if isinstance(detail, str):
            if "already exists" in detail.lower():
                return "Username or email already taken"
            if "invalid" in detail.lower():
                return "Invalid credentials"
            return detail
    except Exception:
        pass
    return "An error occurred. Please try again."


def _clear_remote_vectorstore():
    try:
        token = st.session_state.get("auth_token")
        client_id = st.session_state.get("client_id")
        clear_vectorstore_api(token=token, client_id=client_id)
    except Exception:
        pass


def _clear_anonymous_remote_vectorstore():
    try:
        client_id = st.session_state.get("client_id")
        clear_vectorstore_api(token=None, client_id=client_id)
    except Exception:
        pass


def _hydrate_authenticated_state():
    token = st.session_state.get("auth_token")
    if not token:
        return True

    response = get_session_state(token)
    if response.status_code != 200:
        clear_all_state(st.session_state)
        st.warning("Session expired. Please sign in again.")
        return False

    payload = response.json()
    st.session_state.messages = payload.get("messages", [])
    st.session_state.uploaded_docs = payload.get("uploaded_docs", [])
    persist_session(st.session_state)
    return True


def _open_signin_dialog():
    st.session_state.signin_form_version += 1
    open_signin_dialog()


def _open_register_dialog():
    st.session_state.register_form_version += 1
    open_register_dialog()


@st.dialog("Sign In")
def open_signin_dialog():
    form_version = st.session_state.signin_form_version
    with st.form("signin_form", clear_on_submit=False):
        username_or_email = st.text_input(
            "Username or Email",
            autocomplete="username",
            key=f"signin_username_or_email_{form_version}",
        )
        password = st.text_input(
            "Password",
            type="password",
            autocomplete="current-password",
            key=f"signin_password_{form_version}",
        )
        submitted = st.form_submit_button("Sign In")

    if submitted:
        response = login_user(username_or_email=username_or_email, password=password)
        if response.status_code == 200:
            _clear_anonymous_remote_vectorstore()
            payload = response.json()
            st.session_state.auth_token = payload["access_token"]
            st.session_state.auth_username = payload["username"]
            if _hydrate_authenticated_state():
                st.success("Signed in successfully")
                st.rerun()
        else:
            error_msg = _extract_error_message(response)
            st.error(error_msg)


@st.dialog("Register")
def open_register_dialog():
    form_version = st.session_state.register_form_version
    with st.form("register_form", clear_on_submit=False):
        username = st.text_input("Username", autocomplete="username", key=f"register_username_{form_version}")
        email = st.text_input("Email", autocomplete="email", key=f"register_email_{form_version}")
        password = st.text_input("Password", type="password", autocomplete="new-password", key=f"register_password_{form_version}")
        confirm_password = st.text_input(
            "Confirm Password",
            type="password",
            autocomplete="new-password",
            key=f"register_confirm_password_{form_version}",
        )
        submitted = st.form_submit_button("Create Account")

    if submitted:
        if password != confirm_password:
            st.error("Passwords do not match")
            return

        response = register_user(username=username, email=email, password=password)
        if response.status_code == 200:
            _clear_anonymous_remote_vectorstore()
            payload = response.json()
            st.session_state.auth_token = payload["access_token"]
            st.session_state.auth_username = payload["username"]
            if _hydrate_authenticated_state():
                st.success("Registration successful")
                st.rerun()
        else:
            error_msg = _extract_error_message(response)
            st.error(error_msg)


def render_auth_sidebar():
    with st.sidebar:
        if st.session_state.auth_token:
            profile_response = get_my_profile(st.session_state.auth_token)
            if profile_response.status_code == 200:
                profile = profile_response.json()
                st.divider()
                st.markdown(f"**👤 {profile['username']}**")
                st.markdown(
                    f"<div style='font-size:0.82rem; color:#9ca3af; line-height:1.2; margin-bottom:24px;'>{profile['email']}</div>",
                    unsafe_allow_html=True,
                )
                if st.button("Logout", use_container_width=True, key="logout_btn"):
                    clear_all_state(st.session_state)
                    st.rerun()
            else:
                clear_all_state(st.session_state)
                st.warning("Session expired. Please sign in again.")
                st.rerun()
        else:
            st.divider()
            col1, col2 = st.columns(2, gap="small")
            with col1:
                if st.button("Sign In", use_container_width=True, key="signin_btn"):
                    _open_signin_dialog()
            with col2:
                if st.button("Register", use_container_width=True, key="register_btn"):
                    _open_register_dialog()

        if st.button("Clear Chat", use_container_width=True, key="clear_chat_btn"):
            response = clear_vectorstore_api(
                token=st.session_state.get("auth_token"),
                client_id=st.session_state.get("client_id"),
            )
            if response.status_code == 200:
                clear_chat_state(st.session_state)
                st.rerun()
            else:
                st.error(response.text)


init_auth_state()
render_sidebar_auth_style()
render_uploader()
render_chat()
render_history_download()
render_auth_sidebar()
persist_session(st.session_state)
