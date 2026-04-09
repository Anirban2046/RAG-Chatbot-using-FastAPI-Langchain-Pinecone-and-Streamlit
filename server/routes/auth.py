from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.orm import Session
from db import get_db
from models.user import User
from modules.auth import hash_password, authenticate_user, create_access_token, get_current_user
from schemas.auth import RegisterRequest, LoginRequest, AuthResponse, UserProfile
from modules.profile_store import clear_profile_photo, save_profile_photo, profile_photo_path

router = APIRouter(prefix="/auth", tags=["auth"])


def _profile_response(user: User) -> UserProfile:
    photo_path = profile_photo_path(user)
    return UserProfile(
        full_name=user.full_name,
        username=user.username,
        email=user.email,
        has_photo=bool(photo_path and photo_path.exists()),
    )


@router.post("/register", response_model=AuthResponse)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    existing = db.query(User).filter((User.username == payload.username) | (User.email == payload.email)).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username or email already exists")

    user = User(
        username=payload.username,
        email=payload.email,
        hashed_password=hash_password(payload.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(str(user.id))
    return AuthResponse(access_token=token, username=user.username)


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = authenticate_user(db, payload.username_or_email, payload.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    token = create_access_token(str(user.id))
    return AuthResponse(access_token=token, username=user.username)


@router.get("/me", response_model=UserProfile)
def me(user: User = Depends(get_current_user)):
    return _profile_response(user)


@router.get("/me/photo")
def me_photo(user: User = Depends(get_current_user)):
    photo_path = profile_photo_path(user)
    if photo_path is None or not photo_path.exists():
        return JSONResponse(status_code=404, content={"error": "Profile photo not found"})

    media_type = user.profile_photo_mime or "image/jpeg"
    return FileResponse(path=str(photo_path), media_type=media_type, filename=photo_path.name)


@router.patch("/me", response_model=UserProfile)
async def update_me(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    full_name: str = Form(""),
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(""),
    confirm_password: str = Form(""),
    photo: UploadFile | None = File(default=None),
):
    username = username.strip()
    email = email.strip()
    full_name = full_name.strip()

    if not username:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username cannot be empty")
    if not email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email cannot be empty")
    if password or confirm_password:
        if password != confirm_password:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Passwords do not match")
        if len(password) < 6:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password must be at least 6 characters long")

    existing_username = (
        db.query(User)
        .filter(User.username == username, User.id != user.id)
        .first()
    )
    if existing_username:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username already exists")

    existing_email = (
        db.query(User)
        .filter(User.email == email, User.id != user.id)
        .first()
    )
    if existing_email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already exists")

    user.full_name = full_name or None
    user.username = username
    user.email = email

    if password:
        user.hashed_password = hash_password(password)

    if photo is not None and photo.filename:
        save_profile_photo(user, photo)
    elif photo is not None and not photo.filename:
        clear_profile_photo(user)

    db.commit()
    db.refresh(user)
    return _profile_response(user)
