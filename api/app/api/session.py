"""
Secure session management utilities for OAuth2 flow.
"""

import json
import logging
import secrets
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from starlette.middleware.sessions import SessionMiddleware
from starlette.requests import Request

logger = logging.getLogger(__name__)


class DateTimeAwareJSONEncoder(json.JSONEncoder):
    """JSON encoder that handles datetime objects."""

    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


def parse_datetime_in_dict(data: Any) -> Any:
    """Recursively parse ISO datetime strings back to datetime objects."""
    if isinstance(data, dict):
        result = {}
        for key, value in data.items():
            if key == "created_at" and isinstance(value, str):
                try:
                    result[key] = datetime.fromisoformat(value)
                except ValueError:
                    result[key] = value
            else:
                result[key] = parse_datetime_in_dict(value)
        return result
    elif isinstance(data, list):
        return [parse_datetime_in_dict(item) for item in data]
    else:
        return data


class SecureSessionManager:
    """Secure session management using signed cookies."""

    def __init__(self, secret_key: str, max_age: int = 3600):
        """
        Initialize session manager with signing key.

        Args:
            secret_key: Secret key for signing session cookies
            max_age: Session expiration time in seconds
        """
        # Use custom serializer with datetime-aware JSON encoder
        self.serializer = URLSafeTimedSerializer(
            secret_key, serializer_kwargs={"cls": DateTimeAwareJSONEncoder}
        )
        self.max_age = max_age

    def get_session_data(self, request: Request, key: str) -> Any | None:
        """
        Safely retrieve data from session.

        Args:
            request: FastAPI request object
            key: Session key to retrieve

        Returns:
            Session data if exists and valid, None otherwise
        """
        try:
            session_data = request.session.get(key)
            if session_data is None:
                return None

            # Verify signature and expiration
            verified_data = self.serializer.loads(session_data, max_age=self.max_age)

            # Parse datetime strings back to datetime objects
            verified_data = parse_datetime_in_dict(verified_data)
            return verified_data

        except (BadSignature, SignatureExpired) as e:
            logger.warning(f"Invalid session data for key {key}: {e}")
            # Clear invalid session data
            if key in request.session:
                del request.session[key]
            return None
        except Exception as e:
            logger.error(f"Error retrieving session data: {e}")
            return None

    def set_session_data(self, request: Request, key: str, data: Any) -> None:
        """
        Securely store data in session with signature.

        Args:
            request: FastAPI request object
            key: Session key to store
            data: Data to store in session
        """
        try:
            # Sign and serialize the data
            signed_data = self.serializer.dumps(data)
            request.session[key] = signed_data

        except Exception as e:
            logger.error(f"Error storing session data: {e}")
            raise

    def clear_session_data(self, request: Request, key: str) -> None:
        """
        Clear specific session data.

        Args:
            request: FastAPI request object
            key: Session key to clear
        """
        try:
            if key in request.session:
                del request.session[key]

        except Exception as e:
            logger.error(f"Error clearing session data: {e}")

    def clear_all_session_data(self, request: Request) -> None:
        """
        Clear all session data.

        Args:
            request: FastAPI request object
        """
        try:
            request.session.clear()

        except Exception as e:
            logger.error(f"Error clearing all session data: {e}")

    def get_or_create_csrf_token(self, request: Request) -> str:
        """
        Get existing or create new CSRF token.

        Args:
            request: FastAPI request object

        Returns:
            CSRF token string
        """
        token = self.get_session_data(request, "csrf_token")
        if not token:
            token = secrets.token_urlsafe(32)
            self.set_session_data(request, "csrf_token", token)
        return token

    def validate_csrf_token(self, request: Request, token: str) -> bool:
        """
        Validate CSRF token from request.

        Args:
            request: FastAPI request object
            token: CSRF token to validate

        Returns:
            True if token is valid, False otherwise
        """
        stored_token = self.get_session_data(request, "csrf_token")
        return stored_token and secrets.compare_digest(stored_token, token)

    def store_api_key(self, request: Request, api_key: str) -> None:
        """
        Securely store API key with additional validation.

        Args:
            request: FastAPI request object
            api_key: API key to store
        """
        # Clear any existing key first
        self.clear_session_data(request, "openai_api_key")
        # Store with signed serialization
        self.set_session_data(request, "openai_api_key", api_key)

    def get_api_key(self, request: Request) -> str | None:
        """
        Retrieve API key with validation.

        Args:
            request: FastAPI request object

        Returns:
            API key if exists and valid, None otherwise
        """
        return self.get_session_data(request, "openai_api_key")


@asynccontextmanager
async def oauth_session_context(
    request: Request, session_manager: SecureSessionManager
) -> AsyncGenerator[dict[str, Any], None]:
    """
    Context manager for OAuth session management.

    Args:
        request: FastAPI request object
        session_manager: Session manager instance

    Yields:
        OAuth session dictionary for reading/writing
    """
    oauth_data = session_manager.get_session_data(request, "oauth_session") or {}

    try:
        yield oauth_data

    finally:
        # Save any changes back to session
        if oauth_data:
            session_manager.set_session_data(request, "oauth_session", oauth_data)
        else:
            session_manager.clear_session_data(request, "oauth_session")


@asynccontextmanager
async def openai_session_context(
    request: Request, session_manager: SecureSessionManager
) -> AsyncGenerator[dict[str, Any], None]:
    """
    Context manager for OpenAI API key session management.

    Args:
        request: FastAPI request object
        session_manager: Session manager instance

    Yields:
        OpenAI session dictionary for reading/writing
    """
    openai_data = session_manager.get_session_data(request, "openai_session") or {}

    try:
        yield openai_data

    finally:
        # Save any changes back to session
        if openai_data:
            session_manager.set_session_data(request, "openai_session", openai_data)
        else:
            session_manager.clear_session_data(request, "openai_session")


def get_session_middleware(secret_key: str):
    """
    Get session middleware class for configuration.

    Args:
        secret_key: Secret key for session signing

    Returns:
        SessionMiddleware class
    """
    return SessionMiddleware
