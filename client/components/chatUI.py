import streamlit as st
from utils.api import ask_question
from utils.state import persist_session


def render_chat():
    st.subheader("💬 Chat with your assistant")
    token = st.session_state.get("auth_token")
    client_id = st.session_state.get("client_id")

    if "messages" not in st.session_state:
        st.session_state.messages=[]

    # render existing chat history
    for msg in st.session_state.messages:
        st.chat_message(msg["role"]).markdown(msg["content"])

    # input and response
    user_input=st.chat_input("Type your question....")
    if user_input:
        st.chat_message("user").markdown(user_input)
        st.session_state.messages.append({"role":"user","content":user_input})
        persist_session(st.session_state)

        response=ask_question(user_input, token=token, client_id=client_id)
        if response.status_code==200:
            data=response.json()
            answer=data["response"]
            sources=data.get("sources",[])
            st.chat_message("assistant").markdown(answer)
            # if sources:
            #     st.markdown("📄 **Sources: **")
            #     for src in sources:
            #         st.markdown(f"- `{src}`")
            st.session_state.messages.append({"role":"assistant","content":answer})
            persist_session(st.session_state)
        else:
            st.error(f"Error: {response.text}")