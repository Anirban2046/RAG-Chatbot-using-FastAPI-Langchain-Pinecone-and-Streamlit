import streamlit as st
import base64

from utils.api import get_pdf_preview_api, upload_pdfs_api, delete_pdf_api
from utils.state import persist_session


@st.dialog("PDF Preview", width="large")
def show_pdf_preview_dialog(filename: str, token: str | None, client_id: str | None):
    error_container = st.empty()
    response = get_pdf_preview_api(filename=filename, token=token, client_id=client_id)
    if response.status_code != 200:
        error_container.error(f"Unable to preview PDF: {response.text}")
        return

    encoded_pdf = base64.b64encode(response.content).decode("ascii")
    st.markdown(f"**{filename}**")
    st.markdown(
        f'<iframe src="data:application/pdf;base64,{encoded_pdf}" width="100%" height="700" style="border:none;"></iframe>',
        unsafe_allow_html=True,
    )
    st.download_button(
        "Download PDF",
        data=response.content,
        file_name=filename,
        mime="application/pdf",
        width="stretch",
    )


def render_uploader():
    st.markdown('<div class="sidebar-panel-title">Documents</div>', unsafe_allow_html=True)
    token = st.session_state.get("auth_token")
    client_id = st.session_state.get("client_id")
    upload_error_container = st.empty()

    uploaded_files = st.file_uploader(
        "Add PDFs",
        type="pdf",
        accept_multiple_files=True,
        label_visibility="visible",
    )
    if st.button("Upload", width="stretch", key="upload_pdf_btn") and uploaded_files:
        response = upload_pdfs_api(uploaded_files, token=token, client_id=client_id)
        if response.status_code == 200:
            try:
                payload = response.json()
            except Exception:
                payload = {}
            st.session_state.uploaded_docs = payload.get("uploaded_docs", [f.name for f in uploaded_files])
            persist_session(st.session_state)
            st.success("Uploaded successfully")
            st.rerun()
        else:
            upload_error_container.error(f"Upload failed: {response.text}")

    uploaded_docs = st.session_state.get("uploaded_docs", [])
    if not uploaded_docs:
        st.caption("No PDFs uploaded in this session.")
        return

    with st.expander(f"Uploaded in this session ({len(uploaded_docs)})", expanded=False):
        for idx, name in enumerate(uploaded_docs):
            row = st.container(border=True)
            with row:
                st.caption(f"{idx + 1}. {name}")
                col_preview, col_delete = st.columns(2, gap="small")
                with col_preview:
                    if st.button("Preview", key=f"preview_pdf_{idx}_{name}", width="stretch"):
                        show_pdf_preview_dialog(name, token, client_id)
                with col_delete:
                    if st.button("Delete", key=f"delete_pdf_{idx}_{name}", width="stretch"):
                        response = delete_pdf_api(filename=name, token=token, client_id=client_id)
                        if response.status_code == 200:
                            try:
                                payload = response.json()
                                st.session_state.uploaded_docs = payload.get("uploaded_docs", [])
                            except Exception:
                                st.session_state.uploaded_docs = []
                            persist_session(st.session_state)
                            st.rerun()
                        else:
                            st.error(f"Error deleting PDF: {response.text}")
