"""Browser identity storage with cross-browser compatibility.

Anonymous and authenticated content state is persisted in backend DB tables.
The browser stores only identity cookies used to address the server-side state.
"""

import streamlit as st

CLIENT_ID_COOKIE_NAME = "ragchat_client_id"
AUTH_TOKEN_COOKIE_NAME = "ragchat_auth_token"
AUTH_DISABLED_COOKIE_NAME = "ragchat_auth_disabled"

# Streamlit session_state keys for fallback storage
_SS_KEY_CLIENT_ID = "_browser_storage_client_id"
_SS_KEY_AUTH_TOKEN = "_browser_storage_auth_token"
_SS_KEY_AUTH_DISABLED = "_browser_storage_auth_disabled"


def _safe_js(value: str | None) -> str:
    """Safely convert Python value to JavaScript literal."""
    return repr(value or "")


def _set_cookie_script(cookie_name: str, cookie_value: str | None, max_age_seconds: int) -> str:
    """Generate cross-browser JavaScript for setting cookies and localStorage fallback."""
    return f"""
    <script>
    (function() {{
        const cookieName = {_safe_js(cookie_name)};
        const cookieValue = {_safe_js(cookie_value)};
        const maxAge = cookieValue ? {max_age_seconds} : 0;
        
        // Try to set cookie with proper attributes for all browsers
        try {{
            const expires = cookieValue ? `; Max-Age=${{maxAge}}; expires=${{new Date(Date.now() + maxAge * 1000).toUTCString()}}` : '; Max-Age=0';
            const secure = window.location.protocol === 'https:' ? '; Secure' : '';
            const sameSite = '; SameSite=Lax';
            const target = window.parent && window.parent.document ? window.parent.document : document;
            
            // Set on both possible locations for iframe compatibility
            target.cookie = `${{cookieName}}=${{cookieValue || ''}}; Path=/${{expires}}${{secure}}${{sameSite}}`;
            if (target !== document) {{
                document.cookie = `${{cookieName}}=${{cookieValue || ''}}; Path=/${{expires}}${{secure}}${{sameSite}}`;
            }}
        }} catch(e) {{}}
        
        // Fallback: Also store in localStorage for browsers with cookie restrictions
        try {{
            if (cookieValue) {{
                localStorage.setItem(cookieName, cookieValue);
            }} else {{
                localStorage.removeItem(cookieName);
            }}
        }} catch(e) {{}}
    }})();
    </script>
    """


def _write_browser_cookie(cookie_name: str, cookie_value: str | None, max_age_seconds: int) -> None:
    """Write value to cookies and localStorage (for fallback)."""
    st.html(
        _set_cookie_script(cookie_name, cookie_value, max_age_seconds),
        width="stretch",
        unsafe_allow_javascript=True,
    )


def _cookie_value(cookie_name: str) -> str | None:
    """Read cookie value with fallbacks for cross-browser compatibility."""
    # Try 1: Read from Streamlit's cookies (works if accessible)
    try:
        cookies = dict(st.context.cookies)
        value = cookies.get(cookie_name)
        if isinstance(value, str) and value.strip():
            return value.strip()
    except Exception:
        pass
    
    # Try 2: Fallback to Streamlit session_state (works when all else fails)
    ss_key = {
        CLIENT_ID_COOKIE_NAME: _SS_KEY_CLIENT_ID,
        AUTH_TOKEN_COOKIE_NAME: _SS_KEY_AUTH_TOKEN,
        AUTH_DISABLED_COOKIE_NAME: _SS_KEY_AUTH_DISABLED,
    }.get(cookie_name)
    
    if ss_key:
        try:
            value = st.session_state.get(ss_key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        except Exception:
            pass
    
    return None


def get_client_id_from_storage() -> str | None:
    """Read client id from cookie/localStorage/sessionState with fallbacks."""
    value = _cookie_value(CLIENT_ID_COOKIE_NAME)
    if value:
        return value
    
    # Fallback to streamlit session_state if cookie methods failed
    try:
        st.session_state.setdefault(_SS_KEY_CLIENT_ID, None)
        return st.session_state.get(_SS_KEY_CLIENT_ID)
    except Exception:
        return None


def bootstrap_browser_storage() -> None:
    """Restore cookies from localStorage when cookie storage is unavailable.

    Streamlit reads cookies on the Python side, so localStorage must be copied
    back into cookies before the next rerun for the fallback to be effective.
    """
    st.html(
        f"""
        <script>
        (function() {{
            const specs = [
                [{_safe_js(CLIENT_ID_COOKIE_NAME)}, 60 * 60 * 24 * 30],
                [{_safe_js(AUTH_TOKEN_COOKIE_NAME)}, 60 * 60 * 24],
                [{_safe_js(AUTH_DISABLED_COOKIE_NAME)}, 60 * 60 * 24],
            ];

            const cookieNames = new Set(
                document.cookie
                    .split(';')
                    .map((entry) => entry.split('=')[0].trim())
                    .filter(Boolean)
            );

            let restored = false;

            const writeCookie = function(name, value, maxAgeSeconds) {{
                const secure = window.location.protocol === 'https:' ? '; Secure' : '';
                const expires = new Date(Date.now() + maxAgeSeconds * 1000).toUTCString();
                document.cookie = `${{name}}=${{encodeURIComponent(value)}}; Path=/; Max-Age=${{maxAgeSeconds}}; expires=${{expires}}; SameSite=Lax${{secure}}`;
            }};

            for (const [name, maxAgeSeconds] of specs) {{
                if (cookieNames.has(name)) continue;

                try {{
                    const value = localStorage.getItem(name);
                    if (value && value.trim()) {{
                        writeCookie(name, value, maxAgeSeconds);
                        restored = true;
                    }}
                }} catch (e) {{}}
            }}

            if (restored) {{
                window.setTimeout(() => window.location.reload(), 0);
            }}
        }})();
        </script>
        """,
        width="stretch",
        unsafe_allow_javascript=True,
    )


def set_client_id_in_storage(client_id: str) -> None:
    """Persist client id to cookies/localStorage and session_state."""
    # Try cookie storage
    _write_browser_cookie(CLIENT_ID_COOKIE_NAME, client_id, max_age_seconds=60 * 60 * 24 * 30)
    
    # Always backup to session_state as ultimate fallback
    try:
        st.session_state[_SS_KEY_CLIENT_ID] = client_id
    except Exception:
        pass


def get_auth_token_from_storage() -> str | None:
    """Read auth token from cookie/localStorage/sessionState with fallbacks."""
    value = _cookie_value(AUTH_TOKEN_COOKIE_NAME)
    if value:
        return value
    
    # Fallback to streamlit session_state if cookie methods failed
    try:
        st.session_state.setdefault(_SS_KEY_AUTH_TOKEN, None)
        return st.session_state.get(_SS_KEY_AUTH_TOKEN)
    except Exception:
        return None


def set_auth_token_in_storage(token: str | None) -> None:
    """Write auth token to cookies/localStorage and session_state."""
    # Try cookie storage
    _write_browser_cookie(AUTH_TOKEN_COOKIE_NAME, token, max_age_seconds=60 * 60 * 24)
    
    # Always backup to session_state as ultimate fallback
    try:
        st.session_state[_SS_KEY_AUTH_TOKEN] = token
    except Exception:
        pass


def get_auth_disabled_from_storage() -> str | None:
    """Read auth disabled flag from cookie/localStorage/sessionState with fallbacks."""
    value = _cookie_value(AUTH_DISABLED_COOKIE_NAME)
    if value:
        return value
    
    # Fallback to streamlit session_state
    try:
        st.session_state.setdefault(_SS_KEY_AUTH_DISABLED, None)
        return st.session_state.get(_SS_KEY_AUTH_DISABLED)
    except Exception:
        return None


def set_auth_disabled_in_storage(is_disabled: bool) -> None:
    """Write auth disabled flag to cookies/localStorage and session_state."""
    value = "1" if is_disabled else None
    # Try cookie storage
    _write_browser_cookie(AUTH_DISABLED_COOKIE_NAME, value, max_age_seconds=60 * 60 * 24)
    
    # Always backup to session_state as ultimate fallback
    try:
        st.session_state[_SS_KEY_AUTH_DISABLED] = value
    except Exception:
        pass
