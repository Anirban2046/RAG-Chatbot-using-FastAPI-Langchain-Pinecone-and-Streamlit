import re
from pathlib import Path

from fastapi import UploadFile

from logger import logger
from modules.load_vectorstore import UPLOAD_DIR
from models.user import User

PROFILE_PHOTO_ROOT = Path(UPLOAD_DIR) / "profile_photos"


def _user_profile_dir(user: User) -> Path:
    directory = PROFILE_PHOTO_ROOT / f"user-{user.id}"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def profile_photo_path(user: User) -> Path | None:
    if not user.profile_photo_filename:
        return None
    return _user_profile_dir(user) / user.profile_photo_filename


def save_profile_photo(user: User, photo: UploadFile) -> str:
    original_name = Path(photo.filename or "profile-photo").name
    suffix = Path(original_name).suffix.lower() or ".jpg"
    sanitized_stem = re.sub(r"[^a-zA-Z0-9._-]", "_", Path(original_name).stem) or "profile-photo"
    filename = f"{sanitized_stem}{suffix}"
    target_path = _user_profile_dir(user) / filename

    if user.profile_photo_filename:
        existing_path = _user_profile_dir(user) / user.profile_photo_filename
        if existing_path.exists():
            existing_path.unlink(missing_ok=True)

    with open(target_path, "wb") as target_file:
        target_file.write(photo.file.read())

    user.profile_photo_filename = filename
    user.profile_photo_mime = photo.content_type or "image/jpeg"
    return filename


def clear_profile_photo(user: User) -> None:
    if not user.profile_photo_filename:
        return

    existing_path = _user_profile_dir(user) / user.profile_photo_filename
    if existing_path.exists():
        existing_path.unlink(missing_ok=True)

    user.profile_photo_filename = None
    user.profile_photo_mime = None
