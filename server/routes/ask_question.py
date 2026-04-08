from fastapi import APIRouter, Form, Depends, Header
from fastapi.responses import JSONResponse
from modules.llm import get_llm_chain
from modules.query_handlers import query_chain
from langchain_core.documents import Document
from langchain.schema import BaseRetriever
from pinecone import Pinecone
from pydantic import Field
from typing import List
from logger import logger
from modules.auth import get_current_user_optional
from modules.load_vectorstore import (
    _embed_query,
    EmbeddingQuotaExceeded,
    rebuild_vectorstore_from_saved_pdfs,
    cleanup_stale_anonymous_namespaces,
    mark_namespace_active,
)
from modules.principal import resolve_namespace
from models.user import User
from config import PINECONE_API_KEY, PINECONE_INDEX_NAME
from middlewares.exception_handlers import internal_server_error_response

router=APIRouter()

def _fit_vector_dimension(vector, target_dim: int):
    if len(vector) == target_dim:
        return vector
    if len(vector) > target_dim:
        return vector[:target_dim]
    return vector + [0.0] * (target_dim - len(vector))

@router.post("/ask/")
async def ask_question(
    question: str = Form(...),
    user: User | None = Depends(get_current_user_optional),
    x_client_id: str | None = Header(default=None, alias="X-Client-Id"),
):
    try:
        actor = user.username if user else "anonymous"
        namespace = resolve_namespace(user, x_client_id)
        if user is None:
            cleanup_stale_anonymous_namespaces()
            mark_namespace_active(namespace)
        logger.info(f"user={actor} query: {question}")

        # Embed model + Pinecone setup
        pc = Pinecone(api_key=PINECONE_API_KEY)
        index_name = PINECONE_INDEX_NAME
        index = pc.Index(index_name)
        index_info = pc.describe_index(index_name)
        index_dimension = index_info.dimension if hasattr(index_info, "dimension") else index_info.get("dimension", 768)
        try:
            embedded_query = _embed_query(question, namespace=namespace)
        except EmbeddingQuotaExceeded:
            logger.warning("Gemini embedding quota exceeded; rebuilding vector store with fallback embeddings.")
            rebuild_vectorstore_from_saved_pdfs(namespace=namespace, force_fallback=True)
            embedded_query = _embed_query(question, namespace=namespace)
        embedded_query = _fit_vector_dimension(embedded_query, index_dimension)
        res = index.query(vector=embedded_query, top_k=3, include_metadata=True, namespace=namespace)

        docs = [
            Document(
                page_content=match["metadata"].get("text", ""),
                metadata=match["metadata"]
            ) for match in res["matches"]
        ]

        class SimpleRetriever(BaseRetriever):
            docs: List[Document] = Field(default_factory=list)

            def _get_relevant_documents(self, query: str) -> List[Document]:
                return self.docs

        retriever = SimpleRetriever(docs=docs)
        chain = get_llm_chain(retriever)
        result = query_chain(chain, question)

        logger.info("query successful")
        return result
    except ValueError as e:
        return JSONResponse(status_code=400, content={"error": str(e)})

    except Exception as e:
        logger.exception("Error processing question")
        return internal_server_error_response()