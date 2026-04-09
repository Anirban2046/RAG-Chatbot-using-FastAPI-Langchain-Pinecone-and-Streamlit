import requests
from config import API_URL


REQUEST_TIMEOUT_SECONDS = 30


def _error_response(message: str, status_code: int = 503) -> requests.Response:
    response = requests.Response()
    response.status_code = status_code
    response._content = f'{{"error": "{message}"}}'.encode("utf-8")
    response.headers["Content-Type"] = "application/json"
    return response


def _request(method: str, url: str, **kwargs) -> requests.Response:
    kwargs.setdefault("timeout", REQUEST_TIMEOUT_SECONDS)
    try:
        return requests.request(method, url, **kwargs)
    except requests.Timeout:
        return _error_response("Request timed out while contacting the backend.", status_code=504)
    except requests.RequestException as exc:
        return _error_response(f"Unable to reach backend service: {str(exc)}")


def _auth_headers(token: str | None, client_id: str | None = None):
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if client_id:
        headers["X-Client-Id"] = client_id
    return headers


def register_user(username: str, email: str, password: str):
    return _request(
        "POST",
        f"{API_URL}/auth/register",
        json={"username": username, "email": email, "password": password},
    )


def login_user(username_or_email: str, password: str):
    return _request(
        "POST",
        f"{API_URL}/auth/login",
        json={"username_or_email": username_or_email, "password": password},
    )


def get_my_profile(token: str):
    return _request("GET", f"{API_URL}/auth/me", headers=_auth_headers(token))


def get_profile_photo(token: str):
    return _request("GET", f"{API_URL}/auth/me/photo", headers=_auth_headers(token))


def get_session_state(token: str):
    return _request("GET", f"{API_URL}/session/state", headers=_auth_headers(token))


def upload_pdfs_api(files, token: str | None = None, client_id: str | None = None):
    files_payload=[ ("files",(f.name,f.read(),"application/pdf")) for f in files]
    return _request(
        "POST",
        f"{API_URL}/upload_pdfs/",
        files=files_payload,
        headers=_auth_headers(token, client_id),
    )


def ask_question(question, token: str | None = None, client_id: str | None = None):
    return _request(
        "POST",
        f"{API_URL}/ask/",
        data={"question":question},
        headers=_auth_headers(token, client_id),
    )


def clear_vectorstore_api(token: str | None = None, client_id: str | None = None):
    return _request("POST", f"{API_URL}/clear_vectorstore/", headers=_auth_headers(token, client_id))


def delete_pdf_api(filename: str, token: str | None = None, client_id: str | None = None):
    return _request(
        "DELETE",
        f"{API_URL}/delete_pdf/",
        params={"filename": filename},
        headers=_auth_headers(token, client_id),
    )


def get_pdf_preview_api(filename: str, token: str | None = None, client_id: str | None = None):
    return _request(
        "GET",
        f"{API_URL}/preview_pdf/",
        params={"filename": filename},
        headers=_auth_headers(token, client_id),
    )


def update_profile_api(
    token: str,
    data: dict,
    photo=None,
):
    files = {"_multipart": ("", b"", "application/octet-stream")}
    if photo is not None:
        files = {"photo": (photo.name, photo.read(), photo.type or "application/octet-stream")}

    return _request(
        "PATCH",
        f"{API_URL}/auth/me",
        data=data,
        files=files,
        headers=_auth_headers(token),
    )