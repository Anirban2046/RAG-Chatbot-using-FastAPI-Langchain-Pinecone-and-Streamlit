import streamlit as st
from utils.api import upload_pdfs_api
from utils.state import persist_session


def render_uploader():
    st.sidebar.header("Upload documents (.PDFs)")
    token = st.session_state.get("auth_token")
    client_id = st.session_state.get("client_id")

    uploaded_files=st.sidebar.file_uploader("Upload multiple PDFs",type="pdf",accept_multiple_files=True)
    if st.sidebar.button("Upload to Database") and uploaded_files:
        response = upload_pdfs_api(uploaded_files, token=token, client_id=client_id)
        if response.status_code == 200:
            payload = response.json()
            st.session_state.uploaded_docs = payload.get("uploaded_docs", [f.name for f in uploaded_files])
            persist_session(st.session_state)
            st.sidebar.success("Uploaded successfully")
        else:
            st.sidebar.error(f"Error:{response.text}")

    if st.session_state.get("uploaded_docs"):
        st.sidebar.caption("Uploaded PDFs in this session")
        for name in st.session_state["uploaded_docs"]:
            st.sidebar.write(f"- {name}")