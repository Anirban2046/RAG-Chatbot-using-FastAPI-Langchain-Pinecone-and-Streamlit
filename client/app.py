import streamlit as st
import html
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
from utils.state import (
    clear_all_state,
    clear_chat_state,
    persist_session,
    sync_session_from_disk,
    logout_and_reset_state,
)
from utils.browser_storage import (
    bootstrap_browser_storage,
    set_auth_disabled_in_storage,
    set_auth_token_in_storage,
)

try:
    from utils.state import clear_auth_disabled_state
except ImportError:
    def clear_auth_disabled_state(session_state):
        # Backward-compatible fallback for deployments serving an older utils.state module.
        set_auth_disabled_in_storage(False)
        session_state["_ignore_auth_cookie_until"] = 0.0


st.set_page_config(page_title="AI RAG Chatbot", layout="wide")
st.title("RAG Chatbot")
bootstrap_browser_storage()


def init_auth_state():
    sync_session_from_disk(st.session_state)
    st.session_state.setdefault("signin_form_version", 0)
    st.session_state.setdefault("register_form_version", 0)
    st.session_state.setdefault("profile_form_version", 0)
    st.session_state.setdefault("edit_profile_form_version", 0)
    st.session_state.setdefault("profile_dialog_open", False)
    st.session_state.setdefault("edit_profile_dialog_open", False)
    st.session_state.setdefault("current_profile", None)

    token = st.session_state.get("auth_token")
    hydrated_token = st.session_state.get("_hydrated_auth_token")
    if token and token != hydrated_token:
        _hydrate_authenticated_state(suppress_warnings=True)
    elif not token:
        st.session_state["_hydrated_auth_token"] = None


def render_sidebar_auth_style():
    st.markdown(
        """
        <style>
        @media (min-width: 1024px) {
            [data-testid="stSidebar"] {
                min-width: 380px;
                max-width: 380px;
            }
        }
        [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {
            font-size: 0.9rem;
        }
        [data-testid="stSidebar"] .stButton > button {
            min-height: 2.05rem;
            font-size: 0.87rem;
            padding-top: 0.25rem;
            padding-bottom: 0.25rem;
        }
        [data-testid="stSidebar"] .stFileUploader label,
        [data-testid="stSidebar"] .stCaption {
            font-size: 0.82rem;
        }
        .sidebar-panel-title {
            font-size: 0.8rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.04em;
            margin-bottom: 0.35rem;
            opacity: 0.75;
        }
        .profile-chip {
            background: rgba(120, 120, 120, 0.08);
            border: 1px solid rgba(120, 120, 120, 0.25);
            border-radius: 10px;
            padding: 0.55rem 0.6rem;
            margin-bottom: 0.55rem;
        }
        .profile-chip-name {
            font-weight: 600;
            font-size: 0.9rem;
            line-height: 1.2;
        }
        .profile-chip-email {
            font-size: 0.78rem;
            opacity: 0.8;
            line-height: 1.2;
            margin-top: 0.15rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_profile_preview(profile):
    username = html.escape(profile.get("username", "User"))
    email = html.escape(profile.get("email", ""))
    st.markdown(
        f"""
        <div class="profile-chip">
            <div class="profile-chip-name">{username}</div>
            <div class="profile-chip-email">{email.replace('@', '&#64;')}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_profile_dialog_style():
    st.markdown(
        """
        <style>
        .profile-dialog-card {
            border: 1px solid rgba(120, 120, 120, 0.25);
            border-radius: 12px;
            padding: 0.9rem 1rem;
            background: rgba(120, 120, 120, 0.05);
            margin: 0.2rem 0 0.8rem;
        }
        .profile-header-name {
            font-size: 1.08rem;
            font-weight: 700;
            line-height: 1.25;
            margin-bottom: 0.12rem;
        }
        .profile-header-subline {
            font-size: 0.84rem;
            opacity: 0.8;
            line-height: 1.2;
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


def _parse_json_response(response):
    try:
        payload = response.json()
        return payload if isinstance(payload, dict) else None
    except Exception:
        return None


def _hydrate_authenticated_state(suppress_warnings: bool = False):
    token = st.session_state.get("auth_token")
    if not token:
        return True

    response = get_session_state(token)
    if response.status_code != 200:
        clear_all_state(st.session_state)
        if not suppress_warnings:
            st.warning("Session expired. Please sign in again.")
        return False

    payload = _parse_json_response(response)
    if payload is None:
        clear_all_state(st.session_state)
        if not suppress_warnings:
            st.warning("Session data is invalid. Please sign in again.")
        return False

    st.session_state.messages = payload.get("messages", [])
    st.session_state.uploaded_docs = payload.get("uploaded_docs", [])
    st.session_state["_hydrated_auth_token"] = token
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
    error_container = st.empty()
    success_container = st.empty()

    username_or_email = st.text_input(
        "Username or Email",
        autocomplete="username",
        key=f"signin_username_or_email_{form_version}",
        value="",
    )
    password = st.text_input(
        "Password",
        type="password",
        autocomplete="current-password",
        key=f"signin_password_{form_version}",
        value="",
    )

    submitted = st.button("Sign In", key=f"signin_submit_{form_version}", width="stretch")

    if submitted:
        response = login_user(username_or_email=username_or_email, password=password)
        if response.status_code == 200:
            payload = _parse_json_response(response)
            access_token = (payload or {}).get("access_token")
            username = (payload or {}).get("username")
            if not access_token or not username:
                error_container.error("Received an invalid response from server. Please try again.")
                return

            st.session_state.auth_token = access_token
            st.session_state.auth_username = username
            clear_auth_disabled_state(st.session_state)
            set_auth_token_in_storage(access_token)
            if _hydrate_authenticated_state():
                success_container.success("Signed in successfully")
                st.rerun()
        else:
            error_msg = _extract_error_message(response)
            error_container.error(error_msg)


@st.dialog("Register")
def open_register_dialog():
    form_version = st.session_state.register_form_version
    error_container = st.empty()
    success_container = st.empty()

    username = st.text_input(
        "Username",
        autocomplete="username",
        key=f"register_username_{form_version}",
        value="",
    )
    email = st.text_input(
        "Email",
        autocomplete="email",
        key=f"register_email_{form_version}",
        value="",
    )
    password = st.text_input(
        "Password",
        type="password",
        autocomplete="new-password",
        key=f"register_password_{form_version}",
        value="",
    )
    confirm_password = st.text_input(
        "Confirm Password",
        type="password",
        autocomplete="new-password",
        key=f"register_confirm_password_{form_version}",
        value="",
    )

    submitted = st.button("Create Account", key=f"register_submit_{form_version}", width="stretch")

    if submitted:
        if password != confirm_password:
            error_container.error("Passwords do not match")
            return

        response = register_user(username=username, email=email, password=password)
        if response.status_code == 200:
            payload = _parse_json_response(response)
            access_token = (payload or {}).get("access_token")
            username_value = (payload or {}).get("username")
            if not access_token or not username_value:
                error_container.error("Received an invalid response from server. Please try again.")
                return

            st.session_state.auth_token = access_token
            st.session_state.auth_username = username_value
            clear_auth_disabled_state(st.session_state)
            set_auth_token_in_storage(access_token)
            if _hydrate_authenticated_state():
                success_container.success("Registration successful")
                st.rerun()
        else:
            error_msg = _extract_error_message(response)
            error_container.error(error_msg)


@st.dialog("User Profile", width="small")
def open_profile_dialog():
    _render_profile_dialog_style()

    profile = st.session_state.get("current_profile") or {}
    token = st.session_state.get("auth_token")

    display_name_raw = profile.get("full_name") or profile.get("username") or "Not set"
    username = profile.get("username") or "Not set"
    email = profile.get("email") or "Not set"
    subline_raw = f"@{username}" if profile.get("full_name") else "Account profile"
    display_name = html.escape(display_name_raw)
    subline = html.escape(subline_raw)

    col_avatar, col_info = st.columns([1, 2], gap="medium")
    with col_avatar:
        if profile.get("has_photo") and token:
            photo_response = get_profile_photo(token)
            if photo_response.status_code == 200:
                st.image(photo_response.content, width=124)
            else:
                st.markdown(
                    "<div style='font-size:4.2rem; line-height:1; text-align:center; padding-top:0.4rem;'>👤</div>",
                    unsafe_allow_html=True,
                )
        else:
            st.markdown(
                "<div style='font-size:4.2rem; line-height:1; text-align:center; padding-top:0.4rem;'>👤</div>",
                unsafe_allow_html=True,
            )

    with col_info:
        st.markdown(
            f"""
            <div class="profile-dialog-card">
                <div class="profile-header-name">{display_name}</div>
                <div class="profile-header-subline">{subline}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    details_box = st.container(border=True)
    with details_box:
        row1_label, row1_value = st.columns([1, 2], gap="small")
        with row1_label:
            st.caption("Name")
        with row1_value:
            st.text(display_name)

        row2_label, row2_value = st.columns([1, 2], gap="small")
        with row2_label:
            st.caption("Username")
        with row2_value:
            st.text(username)

        row3_label, row3_value = st.columns([1, 2], gap="small")
        with row3_label:
            st.caption("Email")
        with row3_value:
            st.text(email)

    if st.button("Edit Profile", width="stretch", key=f"edit_profile_btn_{st.session_state.profile_form_version}"):
        _open_edit_profile_dialog()


@st.dialog("Edit Profile")
def open_edit_profile_dialog():
    _render_profile_dialog_style()

    profile = st.session_state.get("current_profile") or {}
    token = st.session_state.get("auth_token")
    error_container = st.empty()
    success_container = st.empty()

    form_version = st.session_state.edit_profile_form_version
    full_name = st.text_input(
        "Name",
        value=profile.get("full_name") or "",
        key=f"edit_full_name_{form_version}",
    )
    username = st.text_input(
        "Username",
        value=profile.get("username") or "",
        key=f"edit_username_{form_version}",
    )
    email = st.text_input(
        "Email",
        value=profile.get("email") or "",
        key=f"edit_email_{form_version}",
    )
    photo = st.file_uploader("Photo", type=["png", "jpg", "jpeg", "webp"], key=f"edit_photo_{form_version}")
    password = st.text_input(
        "New Password",
        type="password",
        autocomplete="new-password",
        key=f"edit_password_{form_version}",
        value="",
    )
    confirm_password = st.text_input(
        "Repeat New Password",
        type="password",
        autocomplete="new-password",
        key=f"edit_confirm_password_{form_version}",
        value="",
    )

    col_back, col_save = st.columns(2, gap="small")
    with col_back:
        back_clicked = st.button("Back", width="stretch", key=f"edit_profile_back_{form_version}")
    with col_save:
        submitted = st.button("Save Changes", width="stretch", key=f"edit_profile_save_{form_version}")

    if back_clicked:
        _open_profile_dialog()
        return

    if submitted:
        if password and password != confirm_password:
            error_container.error("Passwords do not match")
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
            updated_profile = _parse_json_response(response)
            if updated_profile is None:
                error_container.error("Received an invalid response from server. Please try again.")
                return

            st.session_state.current_profile = updated_profile
            st.session_state.auth_username = updated_profile.get("username", st.session_state.get("auth_username"))
            if _hydrate_authenticated_state():
                success_container.success("Profile updated successfully")
                st.rerun()
        else:
            error_msg = _extract_error_message(response)
            error_container.error(error_msg)


def render_auth_sidebar():
    with st.sidebar:
        st.markdown('<div class="sidebar-panel-title">Account</div>', unsafe_allow_html=True)
        if st.session_state.auth_token:
            profile_response = get_my_profile(st.session_state.auth_token)
            if profile_response.status_code == 200:
                profile = _parse_json_response(profile_response)
                if profile is None:
                    clear_all_state(st.session_state)
                    st.warning("Session expired. Please sign in again.")
                    return

                st.session_state.current_profile = profile
                _render_profile_preview(profile)

                col1, col2 = st.columns(2, gap="small")
                with col1:
                    if st.button("Profile", width="stretch", key="open_profile_btn"):
                        _open_profile_dialog()
                with col2:
                    if st.button("Logout", width="stretch", key="logout_btn"):
                        logout_and_reset_state(st.session_state)
                        st.rerun()

                if st.button(
                    "Clear Chat",
                    width="stretch",
                    key="clear_chat_btn",
                    help="Removes current chat and uploaded-doc references for this session.",
                ):
                    response = clear_vectorstore_api(
                        token=st.session_state.get("auth_token"),
                        client_id=st.session_state.get("client_id"),
                    )
                    if response.status_code == 200:
                        clear_chat_state(st.session_state)
                        st.rerun()
                    else:
                        st.error(response.text)
            else:
                # Token is invalid but this shouldn't happen if init_auth_state() properly cleared it.
                # Silently handle and continue rather than rerunning mid-render to avoid flicker.
                clear_all_state(st.session_state)
        else:
            col1, col2 = st.columns(2, gap="small")
            with col1:
                if st.button("Sign In", width="stretch", key="signin_btn"):
                    _open_signin_dialog()
            with col2:
                if st.button("Register", width="stretch", key="register_btn"):
                    _open_register_dialog()

            if st.button(
                "Clear Chat",
                width="stretch",
                key="clear_chat_btn",
                help="Removes current chat and uploaded-doc references for this session.",
            ):
                response = clear_vectorstore_api(
                    token=st.session_state.get("auth_token"),
                    client_id=st.session_state.get("client_id"),
                )
                if response.status_code == 200:
                    clear_chat_state(st.session_state)
                    st.rerun()
                else:
                    st.error(response.text)

        st.divider()
        render_uploader()


init_auth_state()
render_sidebar_auth_style()
_render_pending_profile_dialogs()
render_auth_sidebar()
render_chat()
render_history_download()
persist_session(st.session_state)
