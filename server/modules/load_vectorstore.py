import os
import math
import hashlib
import re
import shutil
import time
from pathlib import Path
from tqdm.auto import tqdm
from pinecone import Pinecone, ServerlessSpec
from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from logger import logger
from config import (
    GOOGLE_API_KEY,
    PINECONE_API_KEY,
    PINECONE_ENV,
    PINECONE_INDEX_NAME,
)

os.environ["GOOGLE_API_KEY"] = GOOGLE_API_KEY

UPLOAD_DIR="./uploaded_docs"
os.makedirs(UPLOAD_DIR,exist_ok=True)


# initialize pinecone instance
pc=Pinecone(api_key=PINECONE_API_KEY)
spec=ServerlessSpec(cloud="aws",region=PINECONE_ENV)
existing_indexes=[i["name"] for i in pc.list_indexes()]


if PINECONE_INDEX_NAME not in existing_indexes:
    pc.create_index(
        name=PINECONE_INDEX_NAME,
        dimension=768,
        metric="cosine",
        spec=spec
    )
    while not pc.describe_index(PINECONE_INDEX_NAME).status["ready"]:
        time.sleep(1)


index=pc.Index(PINECONE_INDEX_NAME)
index_info=pc.describe_index(PINECONE_INDEX_NAME)
INDEX_DIMENSION = index_info.dimension if hasattr(index_info, "dimension") else index_info.get("dimension", 768)
EMBEDDING_MODE_BY_NAMESPACE: dict[str, str] = {}


class EmbeddingQuotaExceeded(RuntimeError):
    pass

# load,split,embed and upsert pdf docs content

def _fit_vector_dimension(vector, target_dim: int):
    if len(vector) == target_dim:
        return vector
    if len(vector) > target_dim:
        return vector[:target_dim]
    return vector + [0.0] * (target_dim - len(vector))


def _quota_error_detected(exc: Exception) -> bool:
    message = str(exc).lower()
    return (
        "quota exceeded" in message
        or "please retry in" in message
        or "resource_exhausted" in message
        or "429" in message
        or "embed_content_free_tier_requests" in message
    )


def _hash_text_to_vector(text: str, target_dim: int) -> list[float]:
    vector = [0.0] * target_dim
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    if not tokens:
        return vector

    for token in tokens:
        digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
        index = int.from_bytes(digest[:4], "little") % target_dim
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vector[index] += sign

    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / norm for value in vector]


def _get_embedding_mode(namespace: str) -> str:
    return EMBEDDING_MODE_BY_NAMESPACE.get(namespace, "google")


def _set_embedding_mode(namespace: str, mode: str):
    EMBEDDING_MODE_BY_NAMESPACE[namespace] = mode


def _embed_documents(texts: list[str], namespace: str) -> list[list[float]]:
    if _get_embedding_mode(namespace) == "fallback":
        return [_hash_text_to_vector(text, INDEX_DIMENSION) for text in texts]

    embed_model = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001")
    try:
        embeddings = embed_model.embed_documents(texts)
        return [_fit_vector_dimension(vec, INDEX_DIMENSION) for vec in embeddings]
    except Exception as exc:
        if _quota_error_detected(exc):
            _set_embedding_mode(namespace, "fallback")
            raise EmbeddingQuotaExceeded(str(exc)) from exc
        raise


def _embed_query(text: str, namespace: str) -> list[float]:
    if _get_embedding_mode(namespace) == "fallback":
        return _hash_text_to_vector(text, INDEX_DIMENSION)

    embed_model = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001")
    try:
        embedded_query = embed_model.embed_query(text)
        return _fit_vector_dimension(embedded_query, INDEX_DIMENSION)
    except Exception as exc:
        if _quota_error_detected(exc):
            raise EmbeddingQuotaExceeded(str(exc)) from exc
        raise


def _safe_delete_all_vectors(namespace: str):
    try:
        index.delete(delete_all=True, namespace=namespace)
    except Exception as exc:
        message = str(exc)
        if "Namespace not found" in message or '"code":5' in message:
            return
        raise


def _namespace_upload_dir(namespace: str) -> Path:
    namespace_dir = Path(UPLOAD_DIR) / namespace
    namespace_dir.mkdir(parents=True, exist_ok=True)
    return namespace_dir


def _unique_path_for_filename(namespace_dir: Path, sanitized_name: str) -> Path:
    candidate = namespace_dir / sanitized_name
    if not candidate.exists():
        return candidate

    name_path = Path(sanitized_name)
    stem = name_path.stem
    suffix = name_path.suffix
    counter = 1

    while True:
        candidate = namespace_dir / f"{stem}__{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def _find_best_matching_file(namespace_dir: Path, filename: str) -> Path | None:
    requested_name = Path(filename).name
    sanitized_name = re.sub(r"[^a-zA-Z0-9._-]", "_", requested_name)

    exact_requested = namespace_dir / requested_name
    if exact_requested.exists() and exact_requested.is_file():
        return exact_requested

    exact_sanitized = namespace_dir / sanitized_name
    if exact_sanitized.exists() and exact_sanitized.is_file():
        return exact_sanitized

    stem = Path(sanitized_name).stem
    suffix = Path(sanitized_name).suffix
    pattern = f"{stem}__*{suffix}"
    candidates = [path for path in namespace_dir.glob(pattern) if path.is_file()]
    if not candidates:
        return None

    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0]


def _finalize_staged_pdf(file_path: Path, staging_path: Path):
    if not staging_path.exists():
        return

    if file_path.exists():
        staging_path.unlink(missing_ok=True)
        return

    try:
        staging_path.rename(file_path)
        return
    except Exception as rename_exc:
        logger.warning(
            f"Failed to restore staged PDF {staging_path.name} back to {file_path.name}: {str(rename_exc)}"
        )

    try:
        shutil.copy2(staging_path, file_path)
    except Exception as copy_exc:
        logger.error(
            f"Failed to recover staged PDF {staging_path.name} for {file_path.name}: {str(copy_exc)}"
        )
        raise
    finally:
        staging_path.unlink(missing_ok=True)


def _remove_local_namespace_dir(namespace: str):
    namespace_dir = Path(UPLOAD_DIR) / namespace
    if not namespace_dir.exists() or not namespace_dir.is_dir():
        return

    for nested in namespace_dir.glob("**/*"):
        if nested.is_file():
            nested.unlink(missing_ok=True)
    for nested_dir in sorted(namespace_dir.glob("**/*"), reverse=True):
        if nested_dir.is_dir():
            nested_dir.rmdir()
    namespace_dir.rmdir()


def _save_uploaded_files(uploaded_files, namespace: str):
    file_paths = []
    namespace_dir = _namespace_upload_dir(namespace)
    for file in uploaded_files:
        original_name = Path(file.filename or "").name
        sanitized_name = re.sub(r"[^a-zA-Z0-9._-]", "_", original_name)
        if not sanitized_name:
            sanitized_name = f"upload-{int(time.time())}.pdf"
        save_path = _unique_path_for_filename(namespace_dir, sanitized_name)
        with open(save_path, "wb") as f:
            f.write(file.file.read())
        file_paths.append(str(save_path))
    return file_paths


def _build_index_from_files(file_paths, namespace: str, force_fallback: bool = False):
    if force_fallback:
        _set_embedding_mode(namespace, "fallback")

    _safe_delete_all_vectors(namespace)

    for file_path in file_paths:
        loader = PyPDFLoader(file_path)
        documents = loader.load()

        splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
        chunks = splitter.split_documents(documents)

        texts = [chunk.page_content for chunk in chunks]
        metadatas = []
        for chunk in chunks:
            metadata = dict(chunk.metadata)
            metadata["text"] = chunk.page_content
            metadatas.append(metadata)
        ids = [f"{Path(file_path).stem}-{i}" for i in range(len(chunks))]

        print(f"Embedding {len(texts)} chunks...")
        embeddings = _embed_documents(texts, namespace)

        print("Uploading to Pinecone...")
        with tqdm(total=len(embeddings), desc="Upserting to Pinecone") as progress:
            index.upsert(vectors=zip(ids, embeddings, metadatas), namespace=namespace)
            progress.update(len(embeddings))

        print(f"Upload complete for {file_path}")


def rebuild_vectorstore_from_saved_pdfs(namespace: str, force_fallback: bool = False):
    pdf_paths = sorted(str(path) for path in _namespace_upload_dir(namespace).glob("*.pdf"))
    if not pdf_paths:
        _safe_delete_all_vectors(namespace)
        if force_fallback:
            _set_embedding_mode(namespace, "fallback")
        return
    _build_index_from_files(pdf_paths, namespace=namespace, force_fallback=force_fallback)

def load_vectorstore(uploaded_files, namespace: str):
    file_paths = _save_uploaded_files(uploaded_files, namespace)

    try:
        # Rebuild index from ALL saved PDFs (both old and new) to preserve existing PDFs
        rebuild_vectorstore_from_saved_pdfs(namespace=namespace)
    except EmbeddingQuotaExceeded:
        print("Gemini embedding quota exceeded; switching to fallback embeddings and rebuilding vector store.")
        rebuild_vectorstore_from_saved_pdfs(namespace=namespace, force_fallback=True)

    return file_paths


def delete_pdf_from_vectorstore(namespace: str, filename: str):
    """Delete a single PDF and its vectors from Pinecone and filesystem"""
    try:
        namespace_dir = Path(UPLOAD_DIR) / namespace
        file_path = _find_best_matching_file(namespace_dir, filename)

        if file_path is None:
            # If the file is already missing, keep vectors/files consistent with what is on disk.
            rebuild_vectorstore_from_saved_pdfs(namespace)
            return

        staging_path = file_path.with_name(f"{file_path.name}.deleting-{int(time.time() * 1000)}")
        file_path.rename(staging_path)

        try:
            # Rebuild from the remaining PDFs while the target file is staged out.
            rebuild_vectorstore_from_saved_pdfs(namespace)
        except Exception:
            # Roll back the file and rebuild to restore the previous index state.
            if staging_path.exists() and not file_path.exists():
                try:
                    staging_path.rename(file_path)
                except Exception as restore_file_exc:
                    logger.error(
                        f"Failed to restore staged PDF {staging_path.name} for {filename}: {str(restore_file_exc)}"
                    )
                    raise
            try:
                rebuild_vectorstore_from_saved_pdfs(namespace)
            except Exception as restore_exc:
                logger.error(f"Rollback rebuild failed after delete error for {filename}: {str(restore_exc)}")
            finally:
                _finalize_staged_pdf(file_path, staging_path)
            raise

        if staging_path.exists():
            _finalize_staged_pdf(file_path, staging_path)
        
    except Exception as e:
        logger.error(f"Error deleting PDF {filename} from vectorstore: {str(e)}")
        raise


def clear_vectorstore(namespace: str):
    _safe_delete_all_vectors(namespace)
    _remove_local_namespace_dir(namespace)
    EMBEDDING_MODE_BY_NAMESPACE.pop(namespace, None)