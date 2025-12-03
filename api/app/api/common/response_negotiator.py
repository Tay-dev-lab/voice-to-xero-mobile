"""
Content negotiation utilities for supporting both web (HTML) and mobile (JSON) clients.

This module provides helpers to detect client type based on Accept header
and return appropriate responses.
"""

from collections.abc import Callable
from enum import Enum
from typing import Any

from fastapi import Request
from fastapi.responses import HTMLResponse, JSONResponse


class ClientType(str, Enum):
    """Client type determined from Accept header."""

    WEB = "web"
    MOBILE = "mobile"


def get_client_type(request: Request) -> ClientType:
    """
    Determine client type from Accept header.

    Args:
        request: FastAPI request object

    Returns:
        ClientType.MOBILE if Accept header contains application/json,
        otherwise ClientType.WEB
    """
    accept = request.headers.get("accept", "text/html")
    if "application/json" in accept:
        return ClientType.MOBILE
    return ClientType.WEB


def wants_json(request: Request) -> bool:
    """
    Quick check if client wants JSON response.

    Args:
        request: FastAPI request object

    Returns:
        True if client prefers JSON (mobile), False for HTML (web)
    """
    return get_client_type(request) == ClientType.MOBILE


def dual_response(
    request: Request,
    html_content: str | Callable[[], str],
    json_data: dict[str, Any],
    status_code: int = 200,
) -> HTMLResponse | JSONResponse:
    """
    Return HTML or JSON based on client type.

    Args:
        request: FastAPI request object
        html_content: HTML string or callable that returns HTML
        json_data: Dictionary to return as JSON
        status_code: HTTP status code (default 200)

    Returns:
        HTMLResponse for web clients, JSONResponse for mobile clients
    """
    if wants_json(request):
        return JSONResponse(content=json_data, status_code=status_code)

    content = html_content() if callable(html_content) else html_content
    return HTMLResponse(content=content, status_code=status_code)


def json_success(data: dict[str, Any] | None = None) -> dict[str, Any]:
    """
    Create a standard success response envelope.

    Args:
        data: Optional data payload

    Returns:
        Standardized success response dict
    """
    return {"success": True, "data": data, "error": None}


def json_error(
    code: str,
    message: str,
    field: str | None = None,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Create a standard error response envelope.

    Args:
        code: Error code (e.g., "VALIDATION_ERROR", "AUTH_REQUIRED")
        message: Human-readable error message
        field: Optional field name for validation errors
        details: Optional additional error details

    Returns:
        Standardized error response dict
    """
    error = {"code": code, "message": message}
    if field:
        error["field"] = field
    if details:
        error["details"] = details
    return {"success": False, "data": None, "error": error}
