from fastapi import APIRouter, Depends, Form, Header
from fastapi.responses import JSONResponse
from langchain_core.documents import Document
from langchain.schema import BaseRetriever
from pinecone import Pinecone
from pydantic import Field
from sqlalchemy.orm import Session
from typing import List

from config import PINECONE_API_KEY, PINECONE_INDEX_NAME
from db import get_db
from logger import logger
from modules.auth import get_current_user_optional
from modules.llm import get_llm_chain
from modules.load_vectorstore import (
    EmbeddingQuotaExceeded,
    _embed_query,
    cleanup_stale_anonymous_namespaces,
    mark_namespace_active,
    rebuild_vectorstore_from_saved_pdfs,
)
from modules.principal import resolve_namespace
from modules.query_handlers import query_chain
from modules.user_content_store import save_chat_turn
from models.user import User

router=APIRouter()
NO_DOCS_ERROR = "No documents found. Please upload PDF files first to ask questions."


def _no_docs_response() -> JSONResponse:
    return JSONResponse(status_code=400, content={"error": NO_DOCS_ERROR})

def _fit_vector_dimension(vector, target_dim: int):
    if len(vector) == target_dim:
        return vector
    if len(vector) > target_dim:
        return vector[:target_dim]
    return vector + [0.0] * (target_dim - len(vector))


def _get_namespace_vector_count(index, namespace: str) -> int:
    stats = index.describe_index_stats()
    namespaces = getattr(stats, "namespaces", None)
    if namespaces is None and isinstance(stats, dict):
        namespaces = stats.get("namespaces", {})

    if not isinstance(namespaces, dict):
        return 0

    namespace_stats = namespaces.get(namespace)
    if namespace_stats is None:
        return 0

    if isinstance(namespace_stats, dict):
        return int(namespace_stats.get("vector_count", 0) or 0)

    return int(getattr(namespace_stats, "vector_count", 0) or 0)

@router.post("/ask/")
async def ask_question(
    question: str = Form(...),
    user: User | None = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
    x_client_id: str | None = Header(default=None, alias="X-Client-Id"),
):
    actor = user.username if user else "anonymous"
    try:
        namespace = resolve_namespace(user, x_client_id)

        if user is None:
            try:
                cleanup_stale_anonymous_namespaces()
            except Exception as e:
                logger.warning(f"Cleanup failed (non-fatal): {str(e)}")
            try:
                mark_namespace_active(namespace)
            except Exception as e:
                logger.warning(f"Mark namespace active failed (non-fatal): {str(e)}")
        
        logger.info(f"user={actor} query: {question}")

        # Embed model + Pinecone setup
        pc = Pinecone(api_key=PINECONE_API_KEY)
        index_name = PINECONE_INDEX_NAME
        index = pc.Index(index_name)

        # Guard early: if the namespace has no vectors, return a friendly message.
        try:
            vector_count = _get_namespace_vector_count(index, namespace)
        except Exception as e:
            logger.warning(f"Failed to read index stats for namespace={namespace}: {str(e)}")
            vector_count = 0

        if vector_count == 0:
            logger.info(f"No vectors found for namespace={namespace}; skipping retrieval.")
            return _no_docs_response()

        index_info = pc.describe_index(index_name)
        index_dimension = index_info.dimension if hasattr(index_info, "dimension") else index_info.get("dimension", 768)
        
        try:
            embedded_query = _embed_query(question, namespace=namespace)
        except EmbeddingQuotaExceeded:
            logger.warning("Gemini embedding quota exceeded; rebuilding vector store with fallback embeddings.")
            rebuild_vectorstore_from_saved_pdfs(namespace=namespace, force_fallback=True)
            try:
                embedded_query = _embed_query(question, namespace=namespace)
            except Exception as e:
                logger.warning(f"Failed to embed query after fallback rebuild: {str(e)}")
                return _no_docs_response()
        except Exception as e:
            logger.error(f"Failed to embed query: {str(e)}")
            return _no_docs_response()
            
        embedded_query = _fit_vector_dimension(embedded_query, index_dimension)
        
        try:
            res = index.query(vector=embedded_query, top_k=3, include_metadata=True, namespace=namespace)
        except Exception as e:
            logger.warning(f"Pinecone query for namespace={namespace} failed or returned no results: {str(e)}")
            return _no_docs_response()

        docs = []
        for match in res.get("matches", []):
            metadata = match.get("metadata") or {}
            text = metadata.get("text")
            if not isinstance(text, str) or not text.strip():
                continue
            docs.append(
                Document(
                    page_content=text,
                    metadata=metadata,
                )
            )

        if not docs:
            logger.warning(
                f"No usable documents found in namespace={namespace}; "
                "matches were empty or missing text metadata."
            )
            return _no_docs_response()

        class SimpleRetriever(BaseRetriever):
            docs: List[Document] = Field(default_factory=list)

            def _get_relevant_documents(self, query: str) -> List[Document]:
                return self.docs

        retriever = SimpleRetriever(docs=docs)
        
        try:
            chain = get_llm_chain(retriever)
            result = query_chain(chain, question)
            if user is not None:
                try:
                    save_chat_turn(db, user, question, result.get("response", ""))
                except Exception as e:
                    logger.warning(f"Failed to persist chat history for user={actor}: {str(e)}")
            logger.info("query successful")
            return result
        except Exception as e:
            logger.warning(f"Failed to process query through chain: {str(e)}")
            return _no_docs_response()
    except ValueError as e:
        error_str = str(e)
        logger.error(f"ValueError for user={actor}: {error_str}")
        return JSONResponse(status_code=400, content={"error": error_str})

    except Exception as e:
        logger.exception(f"Error processing question for user={actor}")
        return _no_docs_response()