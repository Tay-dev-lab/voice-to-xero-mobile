"""
Authentication and authorization utilities for contact workflow routes.

This module contains functions for checking authentication status and permissions.
Supports both web session (cookies) and mobile JWT authentication.
"""

from fastapi import HTTPException, Request, status

from app.api.common import MobileAuthManager, extract_bearer_token


def check_auth_status(request: Request) -> tuple[bool, str | None]:
    """
    Check if both Xero and OpenAI are authenticated.
    Supports both mobile JWT tokens and web session cookies.

    Args:
        request: FastAPI request object

    Returns:
        Tuple of (is_authenticated, error_message)
    """
    # First, check for mobile JWT token
    token = extract_bearer_token(request)
    if token:
        # Mobile auth - validate JWT and check mobile session
        mobile_auth = request.app.state.mobile_auth
        payload = mobile_auth.validate_token(token)
        if payload:
            # Check if Xero is connected (required)
            if not payload.xero_connected:
                return False, "Xero authentication required"
            # OpenAI is optional for starting workflow, will be checked during voice processing
            # But we require it to be valid for the workflow
            if not payload.openai_valid:
                return False, "OpenAI API key required"
            return True, None
        else:
            return False, "Invalid or expired token"

    # Fall back to web session (cookies)
    session_manager = request.app.state.session_manager
    xero_token = session_manager.get_session_data(request, "xero_token")
    openai_data = session_manager.get_session_data(request, "openai_session")

    if not xero_token:
        return False, "Xero authentication required"
    if not (openai_data and openai_data.get("is_valid")):
        return False, "OpenAI API key required"

    return True, None


def require_auth_and_csrf(request: Request) -> None:
    """
    Ensure request has valid authentication and CSRF token.

    Raises HTTPException if authentication or CSRF validation fails.

    Args:
        request: FastAPI request object

    Raises:
        HTTPException: 401 if not authenticated, 403 if CSRF invalid
    """
    # Check authentication
    is_auth, error_msg = check_auth_status(request)
    if not is_auth:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=error_msg)

    # Validate CSRF token
    session_manager = request.app.state.session_manager
    csrf_token = request.headers.get("X-CSRF-Token")

    if not session_manager.validate_csrf_token(request, csrf_token):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid CSRF token")


def require_openai_key(request: Request) -> str:
    """
    Get and validate OpenAI API key from session.

    Args:
        request: FastAPI request object

    Returns:
        Valid OpenAI API key

    Raises:
        HTTPException: 401 if OpenAI key not found or invalid
    """
    session_manager = request.app.state.session_manager
    openai_data = session_manager.get_session_data(request, "openai_session")

    if not openai_data or not openai_data.get("is_valid"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="OpenAI API key not configured"
        )

    api_key = openai_data.get("api_key")
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="OpenAI API key not found in session"
        )

    return api_key


def get_xero_access_token(request: Request) -> str:
    """
    Get Xero access token from session.

    Args:
        request: FastAPI request object

    Returns:
        Valid Xero access token

    Raises:
        HTTPException: 401 if Xero token not found
    """
    session_manager = request.app.state.session_manager
    xero_token = session_manager.get_session_data(request, "xero_token")

    if not xero_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Xero authentication required"
        )

    access_token = xero_token.get("access_token")
    if not access_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Xero session")

    return access_token
