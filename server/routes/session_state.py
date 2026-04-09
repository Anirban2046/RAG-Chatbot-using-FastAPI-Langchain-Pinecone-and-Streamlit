from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from db import get_db
from modules.auth import get_current_user
from modules.user_content_store import get_user_content_state
from models.user import User

router = APIRouter(prefix="/session", tags=["session"])


@router.get("/state")
def get_session_state(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return get_user_content_state(db, user)
