from fastapi import APIRouter, Depends, File, Header, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import List

from db import get_db
from logger import logger
from modules.auth import get_current_user_optional
from modules.load_vectorstore import (
    cleanup_stale_anonymous_namespaces,
    clear_vectorstore,
    load_vectorstore,
    mark_namespace_active,
)
from modules.principal import resolve_namespace
from modules.user_content_store import clear_user_content, save_uploaded_documents
from models.user import User


router = APIRouter()


def _run_anonymous_housekeeping(namespace: str, mark_active: bool) -> None:
    try:
        cleanup_stale_anonymous_namespaces()
    except Exception as e:
        logger.warning(f"Cleanup failed (non-fatal): {str(e)}")

    if not mark_active:
        return

    try:
        mark_namespace_active(namespace)
    except Exception as e:
        logger.warning(f"Mark namespace active failed (non-fatal): {str(e)}")


@router.post("/upload_pdfs/")
async def upload_pdfs(
    files: List[UploadFile] = File(...),
    user: User | None = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
    x_client_id: str | None = Header(default=None, alias="X-Client-Id"),
):
    actor = "unknown"
    try:
        actor = user.username if user else "anonymous"
        namespace = resolve_namespace(user, x_client_id)
        if user is None:
            _run_anonymous_housekeeping(namespace, mark_active=True)
        stored_paths = load_vectorstore(files, namespace=namespace)
        if user is not None:
            save_uploaded_documents(db, user, files, stored_paths, namespace)
        logger.info("Document added to vectorstore")
        return {
            "messages": "Files processed and vectorstore updated",
            "uploaded_docs": [file.filename for file in files],
        }
    except ValueError as e:
        logger.error(f"ValueError for user={actor}: {str(e)}")
        return JSONResponse(status_code=400, content={"error": str(e)})
    except Exception as e:
        logger.exception(f"Error during PDF upload for user={actor}")
        return JSONResponse(status_code=400, content={"error": "Failed to upload files"})


@router.post("/clear_vectorstore/")
async def clear_vectorstore_endpoint(
    user: User | None = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
    x_client_id: str | None = Header(default=None, alias="X-Client-Id"),
):
    actor = "unknown"
    try:
        actor = user.username if user else "anonymous"
        namespace = resolve_namespace(user, x_client_id)
        if user is None:
            _run_anonymous_housekeeping(namespace, mark_active=False)
        clear_vectorstore(namespace=namespace)
        if user is not None:
            clear_user_content(db, user)
        logger.info(f"Pinecone vector store cleared for user={actor}")
        return {"message": "Vector store cleared"}
    except ValueError as e:
        logger.error(f"ValueError for user={actor}: {str(e)}")
        return JSONResponse(status_code=400, content={"error": str(e)})
    except Exception as e:
        logger.exception(f"Error clearing Pinecone vector store for user={actor}")
        return JSONResponse(status_code=400, content={"error": "Failed to clear vector store"})
