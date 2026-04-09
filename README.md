# RAG Chatbot
Full-stack, multi-PDF Retrieval-Augmented Generation system with FastAPI, Streamlit, LangChain, Pinecone, and Groq-hosted LLaMA.

## Overview
This project implements an end-to-end RAG chatbot pipeline: a user submits a query from a Streamlit interface, the request is sent to a FastAPI backend, LangChain orchestrates retrieval and generation, embeddings are generated (Google Generative AI embeddings with a fallback strategy), semantic matches are fetched from Pinecone, and a Groq-hosted LLaMA model produces the final context-grounded response.

## Tech Stack
| Category | Technology | Version |
|---|---|---|
| Language Runtime | Python | >=3.12 |
| Backend API | FastAPI | 0.135.3 |
| ASGI Server | Uvicorn | 0.43.0 |
| Frontend UI | Streamlit | 1.56.0 |
| RAG Framework | LangChain stack (`langchain`, `langchain-core`, `langchain-community`) | 0.2.16, 0.2.40, 0.2.16 |
| LLM Provider Integration | Groq via `langchain-groq` | 0.1.5 |
| Embedding Integration | Google Generative AI via `langchain-google-genai` | 1.0.10 |
| Vector Database SDK | Pinecone | 8.1.1 |
| Relational Database | SQLite | 3 (via `sqlite:///./ragchatbot.db`) |
| PDF Parsing | pypdf | 6.9.2 |
| ORM | SQLAlchemy | 2.0.49 |
| Data Validation | Pydantic | 2.12.5 |
| Auth and Security | passlib[argon2], python-jose[cryptography] | 1.7.4, 3.5.0 |

## Features
- Multi-PDF ingestion with upload support from the Streamlit sidebar, including per-file deletion.
- Sidebar authentication dialogs for Register and Sign In.
- In-app PDF preview dialog with inline rendering and download option.
- Document chunking and embedding pipeline for vector indexing.
- Semantic similarity retrieval from Pinecone namespaces.
- Context-aware response generation through a retrieval-augmented LLM chain.
- Chat history persistence for authenticated users (database-backed).
- Session-aware continuity for chat/doc state via client session persistence.
- Editable user profiles (name, username, email, password, profile photo).
- Separation between frontend UI, backend routes, and backend modules for maintainability.

## System Architecture
1. Ingestion: user uploads one or more PDFs from Streamlit; backend stores files under namespace-scoped directories.
2. Parsing and chunking: backend loads PDFs and splits content into retrievable chunks.
3. Embedding: chunks are embedded using `models/gemini-embedding-001` (with fallback embedding mode on quota exhaustion).
4. Indexing: vectors and metadata are upserted into Pinecone under a user/anonymous namespace.
5. Query embedding: user question is embedded using the same namespace embedding strategy.
6. Retrieval: top-k semantically similar chunks are queried from Pinecone.
7. Generation: retrieved context is injected into a LangChain RetrievalQA prompt and answered by Groq-hosted `llama-3.3-70b-versatile`.
8. Persistence: authenticated chat turns and uploaded document metadata are stored in SQLAlchemy-backed tables and restored through session endpoints.

## Project Structure
```text
ragchatbot/
├── main.py                          # Root entry point placeholder
├── pyproject.toml                   # Project metadata and Python version constraint
├── README.md                        # Project documentation
├── client/                          # Streamlit frontend
│   ├── app.py                       # Main Streamlit app (auth, profile, chat composition)
│   ├── config.py                    # Frontend API base URL
│   ├── requirements.txt             # Frontend dependencies
│   ├── components/                  # UI feature components
│   │   ├── chatUI.py                # Chat rendering and question submission
│   │   ├── history_download.py      # Chat history export
│   │   └── upload.py                # Multi-PDF upload and preview UI
│   └── utils/                       # Frontend service/state utilities
│       ├── api.py                   # HTTP client calls to backend endpoints
│       └── state.py                 # Local session persistence and state helpers
├── server/                          # FastAPI backend
│   ├── config.py                    # Environment loading and backend constants
│   ├── db.py                        # SQLAlchemy engine/session setup
│   ├── logger.py                    # Logging configuration
│   ├── main.py                      # FastAPI app initialization and router wiring
│   ├── requirements.txt             # Backend dependencies
│   ├── upload_pdfs.py               # Legacy upload helper utilities
│   ├── middlewares/
│   │   └── exception_handlers.py    # Centralized exception middleware
│   ├── models/
│   │   ├── content.py               # Chat and uploaded-document ORM models
│   │   └── user.py                  # User ORM model
│   ├── modules/                     # Core business logic modules
│   │   ├── auth.py                  # JWT auth, hashing, principal extraction
│   │   ├── llm.py                   # LangChain + Groq RetrievalQA chain builder
│   │   ├── load_vectorstore.py      # PDF loading, embedding, Pinecone indexing/cleanup
│   │   ├── pdf_handlers.py          # File save helper for uploaded PDFs
│   │   ├── principal.py             # Namespace resolution (user vs anonymous)
│   │   ├── profile_store.py         # Profile photo storage helpers
│   │   ├── query_handlers.py        # Chain execution wrapper
│   │   └── user_content_store.py    # Persist/retrieve user chat and upload metadata
│   ├── routes/                      # API endpoints
│   │   ├── ask_question.py          # RAG query endpoint
│   │   ├── auth.py                  # Register/login/profile endpoints
│   │   ├── session_state.py         # Authenticated state hydration endpoint
│   │   └── upload_pdfs.py           # Upload, preview, delete, clear endpoints
│   ├── schemas/
│   │   └── auth.py                  # Pydantic request/response schemas
│   └── uploaded_docs/               # Namespace-scoped uploaded files and profile photos
└── .venv/                           # Local virtual environment (developer-local)
```

## Setup & Installation
1. Clone the repository and enter the project:
```bash
git clone <your-repo-url>
cd ragchatbot
```

2. Create and activate a virtual environment:
```bash
python3 -m venv .venv
source .venv/bin/activate
```

3. Install backend and frontend dependencies:
```bash
pip install -r server/requirements.txt
pip install -r client/requirements.txt
```

4. Create a `.env` file in `server/` (see Environment Variables section).

5. Start the backend API:
```bash
cd server
uvicorn main:app --reload
```

6. In a second terminal, start the Streamlit frontend:
```bash
cd client
streamlit run app.py
```

## Environment Variables
Create `server/.env` with the following keys:

```env
JWT_SECRET_KEY=<your-strong-random-secret-min-32-chars>
GOOGLE_API_KEY=<your-google-generative-ai-api-key>
GROQ_API_KEY=<your-groq-api-key>
PINECONE_API_KEY=<your-pinecone-api-key>
```

| Key | Example Placeholder | Description |
|---|---|---|
| `JWT_SECRET_KEY` | `<strong-random-secret>` | Secret used to sign/verify JWT access tokens. |
| `GOOGLE_API_KEY` | `<google-api-key>` | Credential for Google Generative AI embedding requests. |
| `GROQ_API_KEY` | `<groq-api-key>` | Credential for Groq LLM inference (`llama-3.3-70b-versatile`). |
| `PINECONE_API_KEY` | `<pinecone-api-key>` | Credential for Pinecone vector index operations. |

Additional runtime constants are defined in backend config/module code (for example Pinecone index name/region and CORS origins).

## Usage
The application supports both no-login sessions and signed-in sessions. Use the sidebar Register and Sign In dialogs when you want persisted chat history, uploaded-document metadata, and profile management.

1. Open the Streamlit UI.
2. Choose your access flow from the sidebar.
	- Use Register to create a new account.
	- Use Sign In to open the login dialog for an existing account.
	- Continue without signing in if you only need a temporary session.
3. Upload one or more PDF files from the sidebar.
4. Preview documents in the PDF dialog to validate content before querying.
5. Remove individual PDFs one by one from the uploaded list when needed.
6. Ask questions in the chat input; responses are generated from indexed document context.
7. Use the Clear Chat action in the sidebar to reset the current conversation and start a fresh page state.
8. Review ongoing conversation history and export it via the download action.
9. Update profile details from the profile dialog when signed in.

Internal query lifecycle: user question -> query embedding -> Pinecone top-k retrieval -> context injection into RetrievalQA prompt -> Groq LLaMA answer generation -> optional chat-turn persistence for authenticated users.