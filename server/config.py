import os
from dotenv import load_dotenv

load_dotenv()


def _required_env(name: str) -> str:
	value = os.getenv(name)
	if value is None or not value.strip():
		raise RuntimeError(f"Missing required environment variable: {name}")
	return value.strip()


def _env_int(name: str, default: int, *, minimum: int) -> int:
	value = os.getenv(name)
	if value is None or not value.strip():
		return default
	try:
		parsed = int(value)
	except ValueError:
		return default
	return parsed if parsed >= minimum else default


DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./ragchatbot.db").strip()
JWT_SECRET_KEY = _required_env("JWT_SECRET_KEY")
if JWT_SECRET_KEY.lower() in {"change-me-in-prod", "changeme", "secret"} or len(JWT_SECRET_KEY) < 32:
	raise RuntimeError("JWT_SECRET_KEY is too weak. Use a random secret with at least 32 characters.")

JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = 60

GOOGLE_API_KEY = _required_env("GOOGLE_API_KEY")
GROQ_API_KEY = _required_env("GROQ_API_KEY")
PINECONE_API_KEY = _required_env("PINECONE_API_KEY")
PINECONE_INDEX_NAME = "ragchatbotindex"
PINECONE_ENV = "us-east-1"
CORS_ALLOW_ORIGINS = ["http://localhost:8501", "http://127.0.0.1:8501"]
ANON_NAMESPACE_TTL_HOURS = _env_int("ANON_NAMESPACE_TTL_HOURS", 6, minimum=1)
ANON_CLEANUP_INTERVAL_SECONDS = _env_int("ANON_CLEANUP_INTERVAL_SECONDS", 900, minimum=60)
PROFILE_PHOTO_MAX_BYTES = _env_int("PROFILE_PHOTO_MAX_BYTES", 5 * 1024 * 1024, minimum=1024)
PDF_MAX_FILE_BYTES = _env_int("PDF_MAX_FILE_BYTES", 25 * 1024 * 1024, minimum=1024)
PDF_MAX_FILES_PER_REQUEST = _env_int("PDF_MAX_FILES_PER_REQUEST", 10, minimum=1)
PDF_MAX_TOTAL_BYTES = _env_int("PDF_MAX_TOTAL_BYTES", 100 * 1024 * 1024, minimum=1024)
