"""
JWT token authentication for mobile clients.

This module provides JWT-based authentication as an alternative to session cookies
for React Native mobile clients.
"""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from fastapi import HTTPException, Request
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# JWT configuration
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = 24


class TokenPayload(BaseModel):
    """JWT token payload structure."""

    session_id: str
    xero_connected: bool
    openai_valid: bool
    tenant_id: str | None = None
    exp: datetime
    iat: datetime


class MobileSession(BaseModel):
    """Mobile session data stored server-side."""

    session_id: str
    xero_token: dict[str, Any] | None = None
    openai_api_key: str | None = None
    tenant_id: str | None = None
    created_at: datetime
    last_accessed: datetime


# In-memory storage for mobile sessions (could be replaced with Redis/DB)
_mobile_sessions: dict[str, MobileSession] = {}


class MobileAuthManager:
    """Handle mobile JWT authentication and session management."""

    def __init__(self, secret_key: str, token_expiry_hours: int = JWT_EXPIRY_HOURS):
        """
        Initialize the mobile auth manager.

        Args:
            secret_key: Secret key for JWT signing
            token_expiry_hours: Token validity period in hours
        """
        self.secret_key = secret_key
        self.token_expiry_hours = token_expiry_hours

    def create_token(
        self,
        session_id: str,
        xero_connected: bool = False,
        openai_valid: bool = False,
        tenant_id: str | None = None,
    ) -> str:
        """
        Create JWT token for mobile client.

        Args:
            session_id: Unique session identifier
            xero_connected: Whether Xero is authenticated
            openai_valid: Whether OpenAI key is validated
            tenant_id: Xero tenant ID if connected

        Returns:
            JWT token string
        """
        now = datetime.now(UTC)
        payload = {
            "session_id": session_id,
            "xero_connected": xero_connected,
            "openai_valid": openai_valid,
            "tenant_id": tenant_id,
            "exp": now + timedelta(hours=self.token_expiry_hours),
            "iat": now,
        }
        return jwt.encode(payload, self.secret_key, algorithm=JWT_ALGORITHM)

    def validate_token(self, token: str) -> TokenPayload | None:
        """
        Validate and decode JWT token.

        Args:
            token: JWT token string

        Returns:
            TokenPayload if valid, None if invalid or expired
        """
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[JWT_ALGORITHM])
            return TokenPayload(**payload)
        except jwt.ExpiredSignatureError:
            logger.warning("Mobile token expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid mobile token: {e}")
            return None

    def refresh_token(self, token: str) -> str | None:
        """
        Refresh an existing token with new expiry.

        Args:
            token: Current JWT token

        Returns:
            New JWT token if valid, None if invalid
        """
        payload = self.validate_token(token)
        if not payload:
            return None

        return self.create_token(
            session_id=payload.session_id,
            xero_connected=payload.xero_connected,
            openai_valid=payload.openai_valid,
            tenant_id=payload.tenant_id,
        )

    def create_mobile_session(
        self,
        session_id: str,
        xero_token: dict[str, Any] | None = None,
        openai_api_key: str | None = None,
        tenant_id: str | None = None,
    ) -> MobileSession:
        """
        Create or update a mobile session.

        Args:
            session_id: Session identifier
            xero_token: Xero OAuth token data
            openai_api_key: Validated OpenAI API key
            tenant_id: Xero tenant ID

        Returns:
            MobileSession object
        """
        now = datetime.now(UTC)
        session = MobileSession(
            session_id=session_id,
            xero_token=xero_token,
            openai_api_key=openai_api_key,
            tenant_id=tenant_id,
            created_at=now,
            last_accessed=now,
        )
        _mobile_sessions[session_id] = session
        return session

    def get_mobile_session(self, session_id: str) -> MobileSession | None:
        """
        Get mobile session by ID.

        Args:
            session_id: Session identifier

        Returns:
            MobileSession if found, None otherwise
        """
        session = _mobile_sessions.get(session_id)
        if session:
            session.last_accessed = datetime.now(UTC)
        return session

    def update_mobile_session(
        self,
        session_id: str,
        xero_token: dict[str, Any] | None = None,
        openai_api_key: str | None = None,
        tenant_id: str | None = None,
    ) -> MobileSession | None:
        """
        Update an existing mobile session.

        Args:
            session_id: Session identifier
            xero_token: Xero OAuth token data (if updating)
            openai_api_key: OpenAI API key (if updating)
            tenant_id: Xero tenant ID (if updating)

        Returns:
            Updated MobileSession or None if not found
        """
        session = _mobile_sessions.get(session_id)
        if not session:
            return None

        if xero_token is not None:
            session.xero_token = xero_token
        if openai_api_key is not None:
            session.openai_api_key = openai_api_key
        if tenant_id is not None:
            session.tenant_id = tenant_id
        session.last_accessed = datetime.now(UTC)

        _mobile_sessions[session_id] = session
        return session

    def delete_mobile_session(self, session_id: str) -> bool:
        """
        Delete a mobile session.

        Args:
            session_id: Session identifier

        Returns:
            True if deleted, False if not found
        """
        if session_id in _mobile_sessions:
            del _mobile_sessions[session_id]
            return True
        return False

    def cleanup_expired_sessions(self, max_age_hours: int = 24) -> int:
        """
        Clean up expired mobile sessions.

        Args:
            max_age_hours: Maximum session age in hours

        Returns:
            Number of sessions removed
        """
        now = datetime.now(UTC)
        cutoff = now - timedelta(hours=max_age_hours)
        expired = [
            sid for sid, session in _mobile_sessions.items() if session.last_accessed < cutoff
        ]
        for sid in expired:
            del _mobile_sessions[sid]
        return len(expired)


def extract_bearer_token(request: Request) -> str | None:
    """
    Extract Bearer token from Authorization header.

    Args:
        request: FastAPI request object

    Returns:
        Token string if present, None otherwise
    """
    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:]
    return None


def get_xero_token(request: Request) -> dict | None:
    """
    Get Xero token data from either mobile session or web session.

    Checks for mobile JWT auth first, then falls back to web session cookies.

    Args:
        request: FastAPI request object

    Returns:
        Xero token dict if found, None otherwise
    """
    # First, check for mobile JWT token
    token = extract_bearer_token(request)
    if token:
        mobile_auth: MobileAuthManager = request.app.state.mobile_auth
        payload = mobile_auth.validate_token(token)
        if payload:
            # Get the mobile session to retrieve the Xero token
            session = mobile_auth.get_mobile_session(payload.session_id)
            if session and session.xero_token:
                logger.debug(f"Found Xero token in mobile session {payload.session_id}")
                return session.xero_token
            else:
                logger.warning(
                    f"Mobile session {payload.session_id} exists={session is not None}, "
                    f"has_xero_token={session.xero_token is not None if session else False}"
                )
        else:
            logger.warning("Invalid or expired JWT token for Xero token lookup")
        return None

    # Fall back to web session (cookies)
    session_manager = request.app.state.session_manager
    return session_manager.get_session_data(request, "xero_token")


def get_openai_api_key(request: Request) -> str | None:
    """
    Get OpenAI API key from either mobile session or web session.

    Checks for mobile JWT auth first, then falls back to web session cookies.

    Args:
        request: FastAPI request object

    Returns:
        OpenAI API key if found, None otherwise
    """
    # First, check for mobile JWT token
    token = extract_bearer_token(request)
    if token:
        mobile_auth: MobileAuthManager = request.app.state.mobile_auth
        payload = mobile_auth.validate_token(token)
        if payload:
            # Get the mobile session to retrieve the API key
            session = mobile_auth.get_mobile_session(payload.session_id)
            if session and session.openai_api_key:
                logger.debug(f"Found OpenAI key in mobile session {payload.session_id}")
                return session.openai_api_key
            else:
                logger.warning(
                    f"Mobile session {payload.session_id} exists={session is not None}, "
                    f"has_key={session.openai_api_key is not None if session else False}"
                )
        else:
            logger.warning("Invalid or expired JWT token")
        return None

    # Fall back to web session (cookies)
    session_manager = request.app.state.session_manager
    return session_manager.get_api_key(request)


def require_mobile_auth(
    request: Request, mobile_auth: MobileAuthManager
) -> TokenPayload:
    """
    Dependency to require valid mobile authentication.

    Args:
        request: FastAPI request object
        mobile_auth: MobileAuthManager instance

    Returns:
        TokenPayload if authenticated

    Raises:
        HTTPException: If not authenticated or token invalid
    """
    token = extract_bearer_token(request)
    if not token:
        raise HTTPException(
            status_code=401,
            detail={"code": "AUTH_REQUIRED", "message": "Authorization token required"},
        )

    payload = mobile_auth.validate_token(token)
    if not payload:
        raise HTTPException(
            status_code=401,
            detail={"code": "INVALID_TOKEN", "message": "Invalid or expired token"},
        )

    return payload
