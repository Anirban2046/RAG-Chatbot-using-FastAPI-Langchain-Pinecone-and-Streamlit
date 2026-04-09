import re
from pathlib import Path

from fastapi import APIRouter, Depends, File, Header, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.orm import Session
from typing import List

from config import PDF_MAX_FILE_BYTES, PDF_MAX_FILES_PER_REQUEST, PDF_MAX_TOTAL_BYTES
from db import get_db
from logger import logger
from modules.auth import get_current_user_optional
from modules.load_vectorstore import (
    UPLOAD_DIR,
    _find_best_matching_file,
    cleanup_stale_anonymous_namespaces,
    clear_vectorstore,
    delete_pdf_from_vectorstore,
    load_vectorstore,
    mark_namespace_active,
)
from modules.principal import resolve_namespace
from modules.user_content_store import clear_user_content, save_uploaded_documents
from models.content import UploadedDocument
from models.user import User


router = APIRouter()


def _upload_size_bytes(upload: UploadFile) -> int:
    current_pos = upload.file.tell()
    upload.file.seek(0, 2)
    size = upload.file.tell()
    upload.file.seek(current_pos)
    return int(size)


def _validate_pdf_uploads(files: List[UploadFile]) -> None:
    if len(files) > PDF_MAX_FILES_PER_REQUEST:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Too many files uploaded at once. Maximum allowed is {PDF_MAX_FILES_PER_REQUEST}.",
        )

    total_bytes = 0
    for file in files:
        file_size = _upload_size_bytes(file)
        if file_size > PDF_MAX_FILE_BYTES:
            max_mb = PDF_MAX_FILE_BYTES / (1024 * 1024)
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File '{file.filename}' is too large. Maximum allowed size is {max_mb:.1f} MB.",
            )
        total_bytes += file_size

    if total_bytes > PDF_MAX_TOTAL_BYTES:
        total_mb = PDF_MAX_TOTAL_BYTES / (1024 * 1024)
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Total upload size is too large. Maximum allowed total is {total_mb:.1f} MB.",
        )


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


def _sanitize_filename(filename: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9._-]", "_", Path(filename).name)
    return cleaned or ""


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
        _validate_pdf_uploads(files)
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
    except HTTPException:
        raise
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


@router.get("/preview_pdf/")
async def preview_pdf(
    filename: str = Query(..., min_length=1),
    user: User | None = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
    x_client_id: str | None = Header(default=None, alias="X-Client-Id"),
):
    actor = user.username if user else "anonymous"
    try:
        namespace = resolve_namespace(user, x_client_id)
        namespace_dir = Path(UPLOAD_DIR) / namespace

        candidate_path: Path | None = None
        if user is not None:
            record = (
                db.query(UploadedDocument)
                .filter(
                    UploadedDocument.user_id == user.id,
                    UploadedDocument.namespace == namespace,
                    UploadedDocument.original_filename == filename,
                )
                .order_by(UploadedDocument.created_at.desc(), UploadedDocument.id.desc())
                .first()
            )
            if record:
                candidate_path = namespace_dir / Path(record.stored_filename).name

        if candidate_path is None:
            if not _sanitize_filename(filename):
                return JSONResponse(status_code=404, content={"error": "PDF not found"})
            candidate_path = _find_best_matching_file(namespace_dir, filename)
            if candidate_path is None:
                return JSONResponse(status_code=404, content={"error": "PDF not found"})

        if not candidate_path.exists() or not candidate_path.is_file():
            return JSONResponse(status_code=404, content={"error": "PDF not found"})

        return FileResponse(
            path=str(candidate_path),
            media_type="application/pdf",
            filename=Path(filename).name,
            headers={"Content-Disposition": f'inline; filename="{Path(filename).name}"'},
        )
    except ValueError as e:
        logger.error(f"ValueError for user={actor} on preview: {str(e)}")
        return JSONResponse(status_code=400, content={"error": str(e)})
    except Exception:
        logger.exception(f"Error serving PDF preview for user={actor}")
        return JSONResponse(status_code=400, content={"error": "Failed to preview PDF"})


@router.delete("/delete_pdf/")
async def delete_pdf(
    filename: str = Query(..., min_length=1),
    user: User | None = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
    x_client_id: str | None = Header(default=None, alias="X-Client-Id"),
):
    actor = "unknown"
    try:
        actor = user.username if user else "anonymous"
        namespace = resolve_namespace(user, x_client_id)
        
        # Delete from database if authenticated user
        if user is not None:
            db.query(UploadedDocument).filter(
                UploadedDocument.user_id == user.id,
                UploadedDocument.namespace == namespace,
                UploadedDocument.original_filename == filename,
            ).delete()
            db.commit()
        
        # Delete from Pinecone and filesystem
        delete_pdf_from_vectorstore(namespace, filename)
        
        logger.info(f"PDF {filename} deleted for user={actor}")
        return {"message": f"PDF '{filename}' deleted successfully"}
    except ValueError as e:
        logger.error(f"ValueError for user={actor} on delete: {str(e)}")
        return JSONResponse(status_code=400, content={"error": str(e)})
    except Exception as e:
        logger.exception(f"Error deleting PDF {filename} for user={actor}")
        return JSONResponse(status_code=400, content={"error": "Failed to delete PDF"})
