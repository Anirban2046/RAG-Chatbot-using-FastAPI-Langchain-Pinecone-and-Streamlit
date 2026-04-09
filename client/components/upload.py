import streamlit as st
import base64

from utils.api import get_pdf_preview_api, upload_pdfs_api, delete_pdf_api
from utils.state import persist_session


@st.dialog("PDF Preview", width="large")
def show_pdf_preview_dialog(filename: str, token: str | None, client_id: str | None):
    response = get_pdf_preview_api(filename=filename, token=token, client_id=client_id)
    if response.status_code != 200:
        st.error(f"Unable to preview PDF: {response.text}")
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
            st.rerun()
        else:
            st.sidebar.error(f"Error:{response.text}")

    if st.session_state.get("uploaded_docs"):
        st.sidebar.caption("Uploaded PDFs in this session")
        for idx, name in enumerate(st.session_state["uploaded_docs"]):
            col1, col2 = st.sidebar.columns([3, 1], gap="small")
            with col1:
                if st.button(f"{name}", key=f"preview_pdf_{idx}_{name}", width="stretch", help="Preview this PDF"):
                    show_pdf_preview_dialog(name, token, client_id)
            with col2:
                if st.button("🗑️", key=f"delete_pdf_{idx}_{name}", help="Delete this PDF", width="content"):
                    response = delete_pdf_api(filename=name, token=token, client_id=client_id)
                    if response.status_code == 200:
                        if name in st.session_state.uploaded_docs:
                            st.session_state.uploaded_docs.remove(name)
                        persist_session(st.session_state)
                        st.rerun()
                    else:
                        st.sidebar.error(f"Error deleting PDF: {response.text}")