"""
Common utility functions shared across the application.
"""

from fastapi import Request
from slowapi.util import get_remote_address


def get_session_or_ip(request: Request) -> str:
    """Get session ID for rate limiting, fallback to IP."""
    try:
        session = request.session
        if session and session.get("session_id"):
            return f"session:{session['session_id']}"
    except (AttributeError, KeyError):
        pass
    return get_remote_address(request)
