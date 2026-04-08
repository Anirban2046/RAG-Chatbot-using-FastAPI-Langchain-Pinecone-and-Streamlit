from langchain.prompts import PromptTemplate
from langchain.chains import RetrievalQA
from langchain_groq import ChatGroq
from config import GROQ_API_KEY

# GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

def get_llm_chain(retriever):
    llm = ChatGroq(
        groq_api_key=GROQ_API_KEY,
        model_name="llama-3.3-70b-versatile"
    )

    prompt = PromptTemplate(
        input_variables=["context", "question"],
        template="""
You are a highly capable AI assistant.

Your task is to answer the user's question using ONLY the provided context.

--- 

Context:
{context}

Question:
{question}

---

Instructions:
- Provide a clear, accurate, and concise answer.
- Base your answer strictly on the given context.
- If the answer is not present or cannot be derived from the context, say:
  "The provided context does not contain sufficient information to answer this question."
- Do NOT make up or assume any information.
- If useful, structure the answer in bullet points or steps.
- Maintain a neutral and informative tone.

Answer:
"""
    )

    return RetrievalQA.from_chain_type(
        llm=llm,
        chain_type="stuff",
        retriever=retriever,
        chain_type_kwargs={"prompt": prompt},
        return_source_documents=True
    )