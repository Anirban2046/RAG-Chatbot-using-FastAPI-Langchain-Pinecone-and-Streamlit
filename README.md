# RAG Chatbot using FastAPI, Langchain, Pinecone and Streamlit

## Project Overview

This project is a full-stack Retrieval-Augmented Generation (RAG) chatbot with:

- FastAPI backend for authentication and RAG APIs.
- Streamlit frontend for chat, PDF upload, and session UX.
- LangChain-based retrieval + LLM orchestration.
- Pinecone for vector search.
- JWT auth for registered users.
- Isolated anonymous user namespaces with stale-data cleanup.

The app supports both anonymous and authenticated usage:

- Anonymous users are scoped by `X-Client-Id`.
- Authenticated users are scoped by user id.
- Upload and chat data are isolated per namespace.

## Technologies Used

| Category | Technology | Purpose |
| --- | --- | --- |
| Frontend Framework | Streamlit | Builds the web chat UI and sidebar workflows. |
| Backend Framework | FastAPI | Exposes auth, upload, query, and vectorstore management APIs. |
| Backend Server | Uvicorn | ASGI server for running the FastAPI app. |
| Authentication | JWT (python-jose) | Stateless access tokens for authenticated users. |
| Password Security | Passlib (Argon2) | Secure password hashing and verification. |
| ORM / Data Access | SQLAlchemy | User model persistence and DB session management. |
| Primary Database | SQLite (default) | Stores user accounts and auth metadata. |
| Vector Database | Pinecone | Stores and searches document embeddings by namespace. |
| LLM Orchestration | LangChain | Retrieval pipeline and prompt/chain management. |
| Embeddings | Google Generative AI Embeddings | Converts document chunks and queries into vectors. |
| Chat Model | Groq (Llama model via LangChain) | Generates final grounded answers from retrieved context. |
| Document Parsing | PyPDFLoader (LangChain Community) | Loads PDF content for chunking and indexing. |
| Language | Python | Main implementation language for client and server. |

## Architecture Summary

### Backend (`server/`)

- `main.py`: app bootstrap, CORS, router registration.
- `routes/auth.py`: register, login, profile.
- `routes/upload_pdfs.py`: upload and clear vectorstore APIs.
- `routes/ask_question.py`: question-answering endpoint.
- `modules/load_vectorstore.py`: PDF parsing, chunking, embeddings, Pinecone upsert/query support, anonymous cleanup.
- `modules/auth.py`: password hashing and JWT handling.
- `db.py`, `models/user.py`: SQLAlchemy setup and user model.

### Frontend (`client/`)

- `app.py`: Streamlit app shell, auth dialogs, sidebar actions.
- `components/`: chat UI, uploader, history/download.
- `utils/api.py`: API calls to backend.
- `utils/state.py`: local client/session state persistence.

## Key Features

- Register/login with JWT.
- Protected user profile endpoint (`/auth/me`).
- Upload multiple PDFs and query them via RAG.
- Namespaced retrieval for user isolation.
- Anonymous namespace TTL cleanup to control Pinecone/storage growth.
- Safer error handling (no raw server exception details in API responses).
- Tightened CORS allowlist.

## Prerequisites

- Python 3.12+
- Pinecone account + API key
- Google API key (embeddings)
- Groq API key (LLM)

## Setup

### 1. Create/activate virtual environment

```bash
cd /path/to/ragchatbot
python -m venv .venv
source .venv/bin/activate
```

### 2. Install dependencies

Backend:

```bash
cd server
pip install -r requirements.txt
```

Client:

```bash
cd ../client
pip install -r requirements.txt
```

Dependency notes:

- Both `server/requirements.txt` and `client/requirements.txt` are version-pinned for reproducible installs.
- `uv.lock` is intentionally ignored in this repository because dependency management is done via the two requirements files.

## Environment Variables (`server/.env`)

The backend currently expects only secret/private values in `.env`.

First run:

- Create `server/.env` before starting the backend, otherwise startup will fail due to missing required secrets.

Example:

```dotenv
GOOGLE_API_KEY=your_google_api_key
GROQ_API_KEY=your_groq_api_key
PINECONE_API_KEY=your_pinecone_api_key
JWT_SECRET_KEY=use_a_long_random_secret_at_least_32_chars
```

Notes:

- Non-secret settings (such as DB URL, CORS origins, TTL defaults, index name) are currently defined in `server/config.py`.
- Default DB is SQLite (`sqlite:///./ragchatbot.db`).
- If you move non-secret settings back to env in future, update `server/config.py` accordingly.

## Run the App

### 1. Start FastAPI backend

```bash
cd server
uvicorn main:app --reload
```

Backend default URL: `http://127.0.0.1:8000`

### 2. Start Streamlit frontend

```bash
cd client
streamlit run app.py
```

Frontend default URL: `http://localhost:8501`

## API Endpoints

### Auth

- `POST /auth/register`
- `POST /auth/login`
- `GET /auth/me`

### RAG

- `POST /upload_pdfs/`
- `POST /ask/`
- `POST /clear_vectorstore/`

## Data Isolation and Anonymous Cleanup

- Authenticated namespace: `user-<id>`
- Anonymous namespace: `anon-<client-id>`

Anonymous cleanup behavior:

- Active anonymous namespaces are marked with last-seen timestamps.
- Stale anonymous namespaces are cleaned periodically using TTL + interval logic.
- Cleanup removes both Pinecone vectors and local uploaded docs for stale anonymous namespaces.

This prevents one anonymous user from deleting another user's active data while still controlling storage growth.

## Troubleshooting

### `Address already in use` on port 8000

```bash
lsof -nP -iTCP:8000 -sTCP:LISTEN
kill <pid>
```

Or run backend on a different port:

```bash
uvicorn main:app --reload --port 8001
```

### Missing environment variable errors

Ensure `server/.env` exists and includes all required secret keys.

### Invalid JWT secret

`JWT_SECRET_KEY` must be strong and at least 32 characters.

## Security Notes

- Do not commit real API keys or production secrets.
- Rotate exposed keys immediately.
- Use separate keys and secrets for dev/staging/prod.

