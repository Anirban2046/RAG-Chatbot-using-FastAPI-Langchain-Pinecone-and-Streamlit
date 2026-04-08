from fastapi import APIRouter, UploadFile, File, Depends, Header
from typing import List
from modules.load_vectorstore import (
    load_vectorstore,
    clear_vectorstore,
    cleanup_stale_anonymous_namespaces,
    mark_namespace_active,
)
from fastapi.responses import JSONResponse
from logger import logger
from modules.auth import get_current_user_optional
from modules.principal import resolve_namespace
from models.user import User
from middlewares.exception_handlers import internal_server_error_response


router=APIRouter()

@router.post("/upload_pdfs/")
async def upload_pdfs(
    files:List[UploadFile] = File(...),
    user: User | None = Depends(get_current_user_optional),
    x_client_id: str | None = Header(default=None, alias="X-Client-Id"),
):
    try:
        actor = user.username if user else "anonymous"
        namespace = resolve_namespace(user, x_client_id)
        if user is None:
            cleanup_stale_anonymous_namespaces()
            mark_namespace_active(namespace)
        logger.info(f"user={actor} uploaded files")
        load_vectorstore(files, namespace=namespace)
        logger.info("Document added to vectorstore")
        return {"messages":"Files processed and vectorstore updated"}
    except ValueError as e:
        return JSONResponse(status_code=400, content={"error": str(e)})
    except Exception as e:
        logger.exception("Error during PDF upload")
        return internal_server_error_response()


@router.post("/clear_vectorstore/")
async def clear_vectorstore_endpoint(
    user: User | None = Depends(get_current_user_optional),
    x_client_id: str | None = Header(default=None, alias="X-Client-Id"),
):
    try:
        namespace = resolve_namespace(user, x_client_id)
        if user is None:
            cleanup_stale_anonymous_namespaces()
        clear_vectorstore(namespace=namespace)
        logger.info("Pinecone vector store cleared")
        return {"message": "Vector store cleared"}
    except ValueError as e:
        return JSONResponse(status_code=400, content={"error": str(e)})
    except Exception as e:
        logger.exception("Error clearing Pinecone vector store")
        return internal_server_error_response()