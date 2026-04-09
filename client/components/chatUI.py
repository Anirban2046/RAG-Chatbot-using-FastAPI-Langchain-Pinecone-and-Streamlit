import streamlit as st
from utils.api import ask_question
from utils.state import persist_session


def _render_chat_style():
    st.markdown(
        """
        <style>
        .chat-title {
            font-size: 1.25rem;
            font-weight: 700;
            margin-top: -3.5rem;
            margin-bottom: 0.15rem;
        }
        .welcome-panel {
            border: 1px solid rgba(120, 120, 120, 0.25);
            border-radius: 12px;
            padding: 0.9rem 1rem;
            margin: 0.1rem 0 0.75rem;
            background: rgba(120, 120, 120, 0.04);
        }
        .welcome-panel strong {
            font-size: 0.95rem;
        }
        .welcome-panel p {
            margin: 0.35rem 0 0;
            font-size: 0.85rem;
            line-height: 1.45;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _normalize_error_message(response):
    try:
        error_data = response.json()
        detail = error_data.get("detail")
        if isinstance(detail, list) and detail:
            first = detail[0]
            if isinstance(first, dict):
                return first.get("msg", response.text)
        if isinstance(detail, str) and detail.strip():
            return detail
        return error_data.get("error") or response.text
    except Exception:
        return response.text


def _render_welcome_state(uploaded_count: int):
    docs_line = "No PDFs uploaded yet. Use the left sidebar to upload files." if uploaded_count == 0 else f"{uploaded_count} PDF(s) available in this session."
    st.markdown(
        f"""
        <div class="welcome-panel">
            <strong>Ask anything about your documents</strong>
            <p>{docs_line}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_message(message: dict, index: int):
    role = message.get("role", "assistant")
    content = message.get("content", "")
    avatar = "👤" if role == "user" else "🤖"

    with st.chat_message(role, avatar=avatar):
        st.markdown(content)


def render_chat():
    _render_chat_style()
    st.markdown(
        '<div class="chat-title" style="color:#d1d5db; font-size:16px;">Ask questions grounded in the uploaded PDFs.</div>',
        unsafe_allow_html=True,
    )

    token = st.session_state.get("auth_token")
    client_id = st.session_state.get("client_id")
    uploaded_docs = st.session_state.get("uploaded_docs", [])

    if "messages" not in st.session_state:
        st.session_state.messages = []

    user_input = st.chat_input("Ask a question about your PDFs")
    hide_welcome = st.session_state.get("hide_welcome", False)
    if user_input:
        st.session_state.hide_welcome = True

    if not st.session_state.messages and not hide_welcome and not user_input:
        _render_welcome_state(len(uploaded_docs))

    for idx, msg in enumerate(st.session_state.messages):
        _render_message(msg, idx)

    if user_input:
        user_message = {"role": "user", "content": user_input}
        _render_message(user_message, len(st.session_state.messages))
        st.session_state.messages.append(user_message)
        persist_session(st.session_state)

        with st.spinner("Thinking..."):
            response = ask_question(user_input, token=token, client_id=client_id)

        if response.status_code == 200:
            try:
                data = response.json()
                answer_text = data.get("response", "")
            except Exception:
                answer_text = (response.text or "").strip() or "Received an invalid response from server."
            assistant_message = {
                "role": "assistant",
                "content": answer_text,
            }
            _render_message(assistant_message, len(st.session_state.messages))
            st.session_state.messages.append(assistant_message)
            persist_session(st.session_state)
        else:
            error_msg = _normalize_error_message(response)
            st.error(error_msg)