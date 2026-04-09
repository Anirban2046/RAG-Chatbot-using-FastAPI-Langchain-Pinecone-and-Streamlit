import streamlit as st
from components.upload import render_uploader
from components.history_download import render_history_download
from components.chatUI import render_chat
from utils.api import (
    clear_vectorstore_api,
    get_my_profile,
    get_profile_photo,
    get_session_state,
    login_user,
    register_user,
    update_profile_api,
)
from utils.state import clear_all_state, clear_chat_state, persist_session, sync_session_from_disk
from utils.browser_storage import set_auth_token_in_storage, set_client_id_in_storage, inject_storage_script


st.set_page_config(page_title="AI RAG Chatbot", layout="wide")
st.title("RAG Chatbot")
inject_storage_script()  # Inject localStorage management script at the very top


def init_auth_state():
    sync_session_from_disk(st.session_state)
    st.session_state.setdefault("signin_form_version", 0)
    st.session_state.setdefault("register_form_version", 0)
    st.session_state.setdefault("profile_form_version", 0)
    st.session_state.setdefault("edit_profile_form_version", 0)
    st.session_state.setdefault("profile_dialog_open", False)
    st.session_state.setdefault("edit_profile_dialog_open", False)
    st.session_state.setdefault("current_profile", None)

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


def _open_profile_dialog():
    st.session_state.profile_form_version += 1
    st.session_state.profile_dialog_open = True
    st.rerun()


def _open_edit_profile_dialog():
    st.session_state.edit_profile_form_version += 1
    st.session_state.edit_profile_dialog_open = True
    st.session_state.profile_dialog_open = False
    st.rerun()


def _render_pending_profile_dialogs():
    if st.session_state.get("edit_profile_dialog_open"):
        st.session_state.edit_profile_dialog_open = False
        open_edit_profile_dialog()
    elif st.session_state.get("profile_dialog_open"):
        st.session_state.profile_dialog_open = False
        open_profile_dialog()


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
            payload = response.json()
            access_token = payload["access_token"]
            st.session_state.auth_token = access_token
            st.session_state.auth_username = payload["username"]
            set_auth_token_in_storage(access_token)  # Persist token across page refreshes
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
            payload = response.json()
            access_token = payload["access_token"]
            st.session_state.auth_token = access_token
            st.session_state.auth_username = payload["username"]
            set_auth_token_in_storage(access_token)  # Persist token across page refreshes
            if _hydrate_authenticated_state():
                st.success("Registration successful")
                st.rerun()
        else:
            error_msg = _extract_error_message(response)
            st.error(error_msg)


@st.dialog("User Profile", width="small")
def open_profile_dialog():
    profile = st.session_state.get("current_profile") or {}
    token = st.session_state.get("auth_token")

    display_name = profile.get("full_name") or profile.get("username") or "Not set"
    username = profile.get("username") or "Not set"
    email = profile.get("email") or "Not set"

    if profile.get("has_photo") and token:
        photo_response = get_profile_photo(token)
        if photo_response.status_code == 200:
            st.image(photo_response.content, width=128)
        else:
            st.markdown(
                "<div style='font-size:4.5rem; line-height:1; text-align:left; padding:0.5rem 0 0.25rem;'>👤</div>",
                unsafe_allow_html=True,
            )
    else:
        st.markdown(
            "<div style='font-size:4.5rem; line-height:1; text-align:left; padding:0.5rem 0 0.25rem;'>👤</div>",
            unsafe_allow_html=True,
        )

    st.markdown(f"### {display_name}")
    st.text(f"Username: {username}")
    st.text(f"Email: {email}")

    st.markdown("<div style='height:0.5rem;'></div>", unsafe_allow_html=True)
    if st.button("Edit Profile", width="stretch", key=f"edit_profile_btn_{st.session_state.profile_form_version}"):
        _open_edit_profile_dialog()


@st.dialog("Edit Profile")
def open_edit_profile_dialog():
    profile = st.session_state.get("current_profile") or {}
    token = st.session_state.get("auth_token")

    form_version = st.session_state.edit_profile_form_version
    with st.form("edit_profile_form", clear_on_submit=False):
        full_name = st.text_input("Name", value=profile.get("full_name") or "", key=f"edit_full_name_{form_version}")
        username = st.text_input("Username", value=profile.get("username") or "", key=f"edit_username_{form_version}")
        email = st.text_input("Email", value=profile.get("email") or "", key=f"edit_email_{form_version}")
        photo = st.file_uploader("Photo", type=["png", "jpg", "jpeg", "webp"], key=f"edit_photo_{form_version}")
        password = st.text_input("New Password", type="password", autocomplete="new-password", key=f"edit_password_{form_version}")
        confirm_password = st.text_input(
            "Repeat New Password",
            type="password",
            autocomplete="new-password",
            key=f"edit_confirm_password_{form_version}",
        )
        submitted = st.form_submit_button("Save Changes")

    if submitted:
        if password and password != confirm_password:
            st.error("Passwords do not match")
            return

        response = update_profile_api(
            token=token,
            data={
                "full_name": full_name,
                "username": username,
                "email": email,
                "password": password,
                "confirm_password": confirm_password,
            },
            photo=photo,
        )
        if response.status_code == 200:
            updated_profile = response.json()
            st.session_state.current_profile = updated_profile
            st.session_state.auth_username = updated_profile.get("username", st.session_state.get("auth_username"))
            if _hydrate_authenticated_state():
                st.success("Profile updated successfully")
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
                st.session_state.current_profile = profile
                st.divider()
                
                # Profile section with clear visual hierarchy and interactivity cues
                st.markdown(
                    "<div style='text-align:center; margin-bottom:12px;'><strong>Your Profile</strong></div>",
                    unsafe_allow_html=True,
                )
                
                # Profile button with visual icon to make it more discoverable
                if st.button(
                    f"👤 {profile['username']} ⚙️",
                    width="stretch",
                    key="open_profile_btn",
                    help="Click to view or edit your profile, change password, upload photo, and more"
                ):
                    _open_profile_dialog()
                
                st.markdown(
                    f"<div style='font-size:0.82rem; color:#9ca3af; line-height:1.2; margin-bottom:24px; text-align:center;'>{profile['email'].replace('@', '&#64;')}</div>",
                    unsafe_allow_html=True,
                )
                if st.button("Logout", width="stretch", key="logout_btn"):
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
                if st.button("Sign In", width="stretch", key="signin_btn"):
                    _open_signin_dialog()
            with col2:
                if st.button("Register", width="stretch", key="register_btn"):
                    _open_register_dialog()

        if st.button("Clear Chat", width="stretch", key="clear_chat_btn"):
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
_render_pending_profile_dialogs()
render_uploader()
render_chat()
render_history_download()
render_auth_sidebar()
persist_session(st.session_state)
