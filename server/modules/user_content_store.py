from pathlib import Path

from sqlalchemy.orm import Session

from models.content import ChatMessage, UploadedDocument
from models.user import User


def get_user_content_state(db: Session, user: User) -> dict:
    messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.user_id == user.id)
        .order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc())
        .all()
    )
    uploads = (
        db.query(UploadedDocument)
        .filter(UploadedDocument.user_id == user.id)
        .order_by(UploadedDocument.created_at.asc(), UploadedDocument.id.asc())
        .all()
    )

    return {
        "messages": [{"role": message.role, "content": message.content} for message in messages],
        "uploaded_docs": [upload.original_filename for upload in uploads],
    }


def save_chat_turn(db: Session, user: User, user_question: str, assistant_answer: str) -> None:
    db.add_all(
        [
            ChatMessage(user_id=user.id, role="user", content=user_question),
            ChatMessage(user_id=user.id, role="assistant", content=assistant_answer),
        ]
    )
    db.commit()


def save_uploaded_documents(
    db: Session,
    user: User,
    uploaded_files,
    stored_paths: list[str],
    namespace: str,
) -> None:
    for uploaded_file, stored_path in zip(uploaded_files, stored_paths):
        original_name = Path(uploaded_file.filename or stored_path).name
        stored_name = Path(stored_path).name
        db.add(
            UploadedDocument(
                user_id=user.id,
                original_filename=original_name,
                stored_filename=stored_name,
                namespace=namespace,
            )
        )
    db.commit()


def clear_user_content(db: Session, user: User) -> None:
    db.query(ChatMessage).filter(ChatMessage.user_id == user.id).delete(synchronize_session=False)
    db.query(UploadedDocument).filter(UploadedDocument.user_id == user.id).delete(synchronize_session=False)
    db.commit()
