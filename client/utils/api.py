import requests
from config import API_URL


def _auth_headers(token: str | None, client_id: str | None = None):
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if client_id:
        headers["X-Client-Id"] = client_id
    return headers


def register_user(username: str, email: str, password: str):
    return requests.post(
        f"{API_URL}/auth/register",
        json={"username": username, "email": email, "password": password},
    )


def login_user(username_or_email: str, password: str):
    return requests.post(
        f"{API_URL}/auth/login",
        json={"username_or_email": username_or_email, "password": password},
    )


def get_my_profile(token: str):
    return requests.get(f"{API_URL}/auth/me", headers=_auth_headers(token))


def upload_pdfs_api(files, token: str | None = None, client_id: str | None = None):
    files_payload=[ ("files",(f.name,f.read(),"application/pdf")) for f in files]
    return requests.post(
        f"{API_URL}/upload_pdfs/",
        files=files_payload,
        headers=_auth_headers(token, client_id),
    )


def ask_question(question, token: str | None = None, client_id: str | None = None):
    return requests.post(
        f"{API_URL}/ask/",
        data={"question":question},
        headers=_auth_headers(token, client_id),
    )


def clear_vectorstore_api(token: str | None = None, client_id: str | None = None):
    return requests.post(f"{API_URL}/clear_vectorstore/", headers=_auth_headers(token, client_id))