"""
FastAPI routes for OAuth2 authentication and OpenAI validation.

Supports both web (HTML) and mobile (JSON) clients via content negotiation.
"""

import logging
import uuid

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from app.api.auth import OpenAIValidator, Settings, XeroOAuth2
from app.api.common import (
    ErrorCodes,
    MobileAuthManager,
    extract_bearer_token,
    json_error,
    json_success,
)
from app.api.session import SecureSessionManager, oauth_session_context, openai_session_context

logger = logging.getLogger(__name__)

# Initialize dependencies
settings = Settings()
session_manager = SecureSessionManager(settings.session_secret_key)
xero_oauth = XeroOAuth2(settings)
mobile_auth = MobileAuthManager(settings.session_secret_key)

# Create router
router = APIRouter()


def get_session_manager() -> SecureSessionManager:
    """Dependency to get session manager instance."""
    return session_manager


@router.get("/", response_class=HTMLResponse)
async def landing_page(request: Request) -> HTMLResponse:
    """
    Landing page with authentication status.
    For mobile OAuth flow, shows success/error message after callback.
    """
    try:
        # Check current authentication status
        xero_token = session_manager.get_session_data(request, "xero_token")
        xero_connected = xero_token is not None

        openai_data = session_manager.get_session_data(request, "openai_session")
        openai_valid = bool(openai_data and openai_data.get("is_valid"))

        # Check for query params (success/error messages)
        success = request.query_params.get("success")
        error = request.query_params.get("error")

        # Build status message
        if success == "xero_connected":
            message = "Xero connected successfully! You can now return to the app."
            status_class = "success"
        elif error:
            error_messages = {
                "auth_denied": "Authorization was denied.",
                "token_exchange_failed": "Failed to complete authentication.",
                "callback_error": "Authentication error occurred.",
                "xero_not_configured": "Xero is not configured.",
            }
            message = error_messages.get(error, f"Error: {error}")
            status_class = "error"
        else:
            message = "Voice to Xero API"
            status_class = "info"

        # Return simple HTML (no templates needed for mobile flow)
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <title>Voice to Xero</title>
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, sans-serif;
                       padding: 40px 20px; text-align: center; background: #f5f5f5; }}
                .container {{ max-width: 400px; margin: 0 auto; background: white;
                             padding: 40px; border-radius: 12px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
                .success {{ color: #22c55e; }}
                .error {{ color: #ef4444; }}
                .info {{ color: #3b82f6; }}
                .status {{ margin: 20px 0; padding: 15px; border-radius: 8px; }}
                .status.success {{ background: #dcfce7; }}
                .status.error {{ background: #fee2e2; }}
                h1 {{ color: #1f2937; margin-bottom: 10px; }}
                p {{ color: #6b7280; }}
                .checkmark {{ font-size: 48px; margin-bottom: 20px; }}
            </style>
        </head>
        <body>
            <div class="container">
                {"<div class='checkmark'>✓</div>" if success else ""}
                <h1 class="{status_class}">{message}</h1>
                <div class="status {status_class}">
                    <p>Xero: {"✓ Connected" if xero_connected else "✗ Not connected"}</p>
                    <p>OpenAI: {"✓ Valid" if openai_valid else "✗ Not configured"}</p>
                </div>
                <p>{"Return to the Voice to Xero app to continue." if xero_connected else ""}</p>
            </div>
        </body>
        </html>
        """
        return HTMLResponse(content=html)

    except Exception as e:
        logger.exception(f"Error loading landing page: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.get("/auth/start")
async def start_auth(request: Request) -> RedirectResponse:
    """
    Start Xero OAuth2 PKCE authentication flow.
    Supports mobile param to redirect to deep link after auth.
    """
    try:
        # Check if Xero credentials are properly configured
        if not settings.xero_client_id or settings.xero_client_id == "placeholder_client_id":
            logger.error("Xero Client ID not configured properly")
            return RedirectResponse(url="/?error=xero_not_configured", status_code=302)

        # Check if the client ID looks valid (should be 32 characters)
        if len(settings.xero_client_id) != 32:
            logger.warning(
                f"Xero Client ID may be invalid: {len(settings.xero_client_id)} characters"
            )

        # Check for mobile flag
        is_mobile = request.query_params.get("mobile") == "true"
        redirect_scheme = request.query_params.get("redirect_scheme", "voice-to-xero")

        async with oauth_session_context(request, session_manager) as oauth_data:
            # Store mobile info for callback
            oauth_data["is_mobile"] = is_mobile
            oauth_data["redirect_scheme"] = redirect_scheme

            # Generate authorization URL with PKCE parameters
            auth_url = xero_oauth.create_authorization_url(oauth_data)

            logger.info(f"Starting OAuth2 flow (mobile={is_mobile}), redirecting to Xero")
            return RedirectResponse(url=auth_url, status_code=302)

    except Exception as e:
        logger.exception(f"Error starting OAuth2 flow: {e}")
        # Provide more specific error message
        error_msg = str(e).lower()
        if "client_id" in error_msg:
            return RedirectResponse(url="/?error=invalid_client_id", status_code=302)
        else:
            return RedirectResponse(url="/?error=auth_failed", status_code=302)


@router.get("/auth/callback")
async def auth_callback(
    request: Request, code: str | None = None, state: str | None = None, error: str | None = None
) -> RedirectResponse:
    """
    Handle OAuth2 callback from Xero.
    For mobile clients: generates JWT and passes via deep link URL.
    """
    try:
        # Check for authorization errors
        if error:
            logger.warning(f"OAuth2 authorization error: {error}")
            return RedirectResponse(url="/?error=auth_denied", status_code=302)

        if not code or not state:
            logger.warning("Missing code or state parameter in callback")
            return RedirectResponse(url="/?error=missing_params", status_code=302)

        async with oauth_session_context(request, session_manager) as oauth_data:
            # Get mobile info before exchanging (oauth_data may be cleared)
            is_mobile = oauth_data.get("is_mobile", False)
            redirect_scheme = oauth_data.get("redirect_scheme", "voice-to-xero")

            # Exchange authorization code for token
            token_response = await xero_oauth.exchange_code_for_token(code, state, oauth_data)

            if token_response:
                # Store token in session (for web clients)
                xero_token_data = token_response.model_dump()
                session_manager.set_session_data(request, "xero_token", xero_token_data)

                # Clear OAuth session data as it's no longer needed
                oauth_data.clear()

                logger.info(f"OAuth2 flow completed successfully (mobile={is_mobile})")

                # For mobile clients, create JWT and pass via deep link
                if is_mobile:
                    # Create mobile session and JWT token
                    session_id = str(uuid.uuid4())
                    mobile_auth.create_mobile_session(
                        session_id=session_id,
                        xero_token=xero_token_data,
                        openai_api_key=None,  # Will be set later
                        tenant_id=xero_token_data.get("tenant_id"),
                    )
                    jwt_token = mobile_auth.create_token(
                        session_id=session_id,
                        xero_connected=True,
                        openai_valid=False,
                        tenant_id=xero_token_data.get("tenant_id"),
                    )
                    # Pass token via deep link
                    deep_link = f"{redirect_scheme}://oauth/callback?success=true&token={jwt_token}"
                    return RedirectResponse(url=deep_link, status_code=302)

                return RedirectResponse(url="/?success=xero_connected", status_code=302)
            else:
                logger.error("Failed to exchange code for token")
                if is_mobile:
                    deep_link = f"{redirect_scheme}://oauth/callback?error=token_exchange_failed"
                    return RedirectResponse(url=deep_link, status_code=302)
                return RedirectResponse(url="/?error=token_exchange_failed", status_code=302)

    except Exception as e:
        logger.exception(f"Error in OAuth2 callback: {e}")
        return RedirectResponse(url="/?error=callback_error", status_code=302)


@router.post("/auth/validate-openai")
async def validate_openai_key(
    request: Request,
    api_key: str = Form(...),
) -> HTMLResponse:
    """
    Validate OpenAI API key endpoint - returns HTML for HTMX.
    """
    try:
        # Validate CSRF token
        csrf_token = request.headers.get("X-CSRF-Token")
        if not csrf_token or not session_manager.validate_csrf_token(request, csrf_token):
            return HTMLResponse(
                '<div class="alert alert-error">Invalid CSRF token. Please refresh the page.</div>',
                status_code=403,
            )

        # Validate the API key
        validation_result = await OpenAIValidator.validate_api_key(api_key)

        if validation_result.is_valid:
            # Store validated key using the secure method
            session_manager.store_api_key(request, api_key)

            # Also store validation status in openai_session
            async with openai_session_context(request, session_manager) as openai_data:
                openai_data.update({"is_valid": True, "error_message": None})

            # Return success message HTML
            return HTMLResponse(
                '<div class="alert alert-success">OpenAI API key validated successfully! Refreshing...</div>',
                status_code=200,
            )
        else:
            # Clear any existing invalid key from session
            session_manager.clear_session_data(request, "openai_session")

            # Return error message HTML
            return HTMLResponse(
                f'<div class="alert alert-error">{validation_result.error_message}</div>',
                status_code=400,
            )

    except Exception as e:
        logger.exception(f"Error validating OpenAI API key: {e}")
        return HTMLResponse(
            '<div class="alert alert-error">Validation failed due to server error</div>',
            status_code=500,
        )


@router.get("/auth/status")
async def auth_status(request: Request) -> JSONResponse:
    """
    Get current authentication status for both Xero and OpenAI.
    """
    try:
        # Check Xero connection status
        xero_token = session_manager.get_session_data(request, "xero_token")
        xero_connected = xero_token is not None

        # Check OpenAI validation status
        openai_data = session_manager.get_session_data(request, "openai_session")
        openai_valid = openai_data and openai_data.get("is_valid", False) if openai_data else False

        return JSONResponse(
            {
                "xero_connected": xero_connected,
                "openai_valid": openai_valid,
                "ready_for_operations": xero_connected and openai_valid,
            }
        )

    except Exception as e:
        logger.exception(f"Error checking auth status: {e}")
        return JSONResponse({"error": "Failed to check authentication status"}, status_code=500)


@router.post("/auth/disconnect")
async def disconnect_auth(request: Request) -> RedirectResponse:
    """
    Disconnect from Xero and clear Xero-related session data.
    """
    try:
        # Clear only Xero-related authentication data
        session_manager.clear_session_data(request, "xero_token")
        session_manager.clear_session_data(request, "oauth_session")

        logger.info("User disconnected from Xero")

        # Redirect back to the main page
        return RedirectResponse(url="/", status_code=303)

    except Exception as e:
        logger.exception(f"Error disconnecting: {e}")
        return RedirectResponse(url="/?error=disconnect_failed", status_code=303)


@router.post("/auth/clear-openai")
async def clear_openai_session(request: Request) -> RedirectResponse:
    """
    Clear OpenAI API key from session.
    """
    try:
        session_manager.clear_session_data(request, "openai_session")

        # Redirect back to the main page
        return RedirectResponse(url="/", status_code=303)

    except Exception as e:
        logger.exception(f"Error clearing OpenAI session: {e}")
        return RedirectResponse(url="/?error=clear_failed", status_code=303)


# ============================================================================
# Mobile API Endpoints
# ============================================================================


@router.post("/auth/mobile/token")
async def get_mobile_token(request: Request) -> JSONResponse:
    """
    Exchange web session credentials for a mobile JWT token.

    Mobile clients should call this after completing OAuth2 flow via web browser.
    The JWT token can then be used for subsequent API requests.
    """
    try:
        # Check current authentication status from web session
        xero_token = session_manager.get_session_data(request, "xero_token")
        openai_data = session_manager.get_session_data(request, "openai_session")

        xero_connected = xero_token is not None
        openai_valid = bool(openai_data and openai_data.get("is_valid"))

        if not xero_connected and not openai_valid:
            return JSONResponse(
                json_error(
                    ErrorCodes.AUTH_REQUIRED,
                    "Complete authentication first. Connect Xero and validate OpenAI key.",
                ),
                status_code=401,
            )

        # Create new mobile session
        session_id = str(uuid.uuid4())

        # Store credentials in mobile session (server-side)
        mobile_auth.create_mobile_session(
            session_id=session_id,
            xero_token=xero_token,
            openai_api_key=openai_data.get("api_key") if openai_data else None,
            tenant_id=xero_token.get("tenant_id") if xero_token else None,
        )

        # Create JWT token
        token = mobile_auth.create_token(
            session_id=session_id,
            xero_connected=xero_connected,
            openai_valid=openai_valid,
            tenant_id=xero_token.get("tenant_id") if xero_token else None,
        )

        return JSONResponse(
            json_success(
                {
                    "token": token,
                    "expires_in": 86400,  # 24 hours
                    "token_type": "Bearer",
                    "xero_connected": xero_connected,
                    "openai_valid": openai_valid,
                }
            )
        )

    except Exception as e:
        logger.exception(f"Error creating mobile token: {e}")
        return JSONResponse(
            json_error(ErrorCodes.AUTH_REQUIRED, "Failed to create token"),
            status_code=500,
        )


@router.post("/auth/mobile/refresh")
async def refresh_mobile_token(request: Request) -> JSONResponse:
    """
    Refresh an existing mobile JWT token.

    Requires valid Bearer token in Authorization header.
    Returns new token with extended expiry.
    """
    try:
        token = extract_bearer_token(request)
        if not token:
            return JSONResponse(
                json_error(ErrorCodes.AUTH_REQUIRED, "Authorization token required"),
                status_code=401,
            )

        # Refresh the token
        new_token = mobile_auth.refresh_token(token)
        if not new_token:
            return JSONResponse(
                json_error(ErrorCodes.INVALID_TOKEN, "Invalid or expired token"),
                status_code=401,
            )

        # Get payload to return current auth status
        payload = mobile_auth.validate_token(new_token)

        return JSONResponse(
            json_success(
                {
                    "token": new_token,
                    "expires_in": 86400,
                    "token_type": "Bearer",
                    "xero_connected": payload.xero_connected if payload else False,
                    "openai_valid": payload.openai_valid if payload else False,
                }
            )
        )

    except Exception as e:
        logger.exception(f"Error refreshing mobile token: {e}")
        return JSONResponse(
            json_error(ErrorCodes.INVALID_TOKEN, "Failed to refresh token"),
            status_code=500,
        )


@router.get("/auth/mobile/status")
async def mobile_auth_status(request: Request) -> JSONResponse:
    """
    Get authentication status for mobile client.

    Requires valid Bearer token in Authorization header.
    """
    try:
        token = extract_bearer_token(request)
        if not token:
            return JSONResponse(
                json_error(ErrorCodes.AUTH_REQUIRED, "Authorization token required"),
                status_code=401,
            )

        payload = mobile_auth.validate_token(token)
        if not payload:
            return JSONResponse(
                json_error(ErrorCodes.INVALID_TOKEN, "Invalid or expired token"),
                status_code=401,
            )

        # Get mobile session for additional details
        session = mobile_auth.get_mobile_session(payload.session_id)

        # Verify status by checking actual session (not just JWT claims)
        # This handles the case where session was recreated but JWT wasn't updated
        xero_actually_connected = (
            session is not None
            and session.xero_token is not None
            and session.xero_token.get("access_token") is not None
        )
        openai_actually_valid = (
            session is not None
            and session.openai_api_key is not None
            and len(session.openai_api_key) > 0
        )

        return JSONResponse(
            json_success(
                {
                    "xero_connected": xero_actually_connected,
                    "openai_valid": openai_actually_valid,
                    "ready_for_operations": xero_actually_connected and openai_actually_valid,
                    "tenant_id": payload.tenant_id,
                    "session_active": session is not None,
                }
            )
        )

    except Exception as e:
        logger.exception(f"Error checking mobile auth status: {e}")
        return JSONResponse(
            json_error(ErrorCodes.AUTH_REQUIRED, "Failed to check status"),
            status_code=500,
        )


@router.post("/auth/mobile/validate-openai")
async def mobile_validate_openai(
    request: Request,
    api_key: str = Form(...),
) -> JSONResponse:
    """
    Validate and store OpenAI API key for mobile client.

    Requires valid Bearer token in Authorization header.
    Stores the API key server-side associated with the mobile session.
    """
    try:
        token = extract_bearer_token(request)
        if not token:
            return JSONResponse(
                json_error(ErrorCodes.AUTH_REQUIRED, "Authorization token required"),
                status_code=401,
            )

        payload = mobile_auth.validate_token(token)
        if not payload:
            return JSONResponse(
                json_error(ErrorCodes.INVALID_TOKEN, "Invalid or expired token"),
                status_code=401,
            )

        # Validate the API key
        validation_result = await OpenAIValidator.validate_api_key(api_key)

        if validation_result.is_valid:
            # Update or create mobile session with validated key
            # (Session might not exist if server was restarted)
            session = mobile_auth.get_mobile_session(payload.session_id)
            if session:
                mobile_auth.update_mobile_session(
                    session_id=payload.session_id,
                    openai_api_key=api_key,
                )
            else:
                # Session doesn't exist - create it with the API key
                logger.info(f"Creating new mobile session for OpenAI validation: {payload.session_id}")
                mobile_auth.create_mobile_session(
                    session_id=payload.session_id,
                    openai_api_key=api_key,
                    tenant_id=payload.tenant_id,
                )

            # Update JWT token to reflect new status
            new_token = mobile_auth.create_token(
                session_id=payload.session_id,
                xero_connected=payload.xero_connected,
                openai_valid=True,
                tenant_id=payload.tenant_id,
            )

            return JSONResponse(
                json_success(
                    {
                        "valid": True,
                        "message": "OpenAI API key validated successfully",
                        "token": new_token,
                    }
                )
            )
        else:
            return JSONResponse(
                json_error(
                    ErrorCodes.OPENAI_NOT_VALID,
                    validation_result.error_message or "Invalid API key",
                ),
                status_code=400,
            )

    except Exception as e:
        logger.exception(f"Error validating OpenAI key for mobile: {e}")
        return JSONResponse(
            json_error(ErrorCodes.VALIDATION_ERROR, "Validation failed"),
            status_code=500,
        )
