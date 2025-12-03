"""
Submission routes for contact workflow.
Handles Xero submission and workflow completion.
"""

import logging

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse

from app.api.auth import Settings, XeroOAuth2
from app.api.common import get_xero_token
from app.api.common.response_negotiator import json_error, json_success, wants_json
from app.api.contact_workflow.session_store import get_contact_session
from app.api.contact_workflow.validators import validate_session_id
from app.api.contact_workflow.xero_service import create_xero_contact, get_xero_tenant_id

from .shared_utils import limiter

logger = logging.getLogger(__name__)

router = APIRouter()


async def refresh_xero_token_if_needed(
    request: Request, xero_token_data: dict, settings: Settings
) -> tuple[str, dict | None]:
    """
    Check if token is valid and refresh if needed.

    Returns:
        Tuple of (access_token, updated_token_data)
        updated_token_data will be None if no refresh was needed
    """
    # Extract the access token string
    access_token = xero_token_data.get("access_token")
    refresh_token = xero_token_data.get("refresh_token")

    if not access_token:
        raise ValueError("No access token found in session")

    if not refresh_token:
        logger.warning("No refresh token available for token refresh")
        return access_token, None

    # We'll try the current token first and refresh if we get a 401
    return access_token, None


@router.post("/proceed-to-submit")
async def proceed_to_submit(
    request: Request,
    session_id: str = Form(...),
) -> HTMLResponse:
    """Proceed from review to final submission step."""

    try:
        session = get_contact_session(session_id)

        # Verify all required data is present
        if not session.to_contact_create():
            return HTMLResponse(
                content='<div class="error">Missing required contact information</div>',
                status_code=400,
            )

        # Mark review step as completed now that user has confirmed
        if "review" not in session.completed_steps:
            session.completed_steps.append("review")

        # Advance to final_submit step
        session.current_step = "final_submit"

        # Render submission interface
        html_content = f'''
        <div class="final-submit-section">
            <h2>Ready to Create Contact in Xero</h2>
            
            <div class="contact-preview">
                <h3>Contact Information:</h3>
                <ul>
                    <li><strong>Name:</strong> {session.contact_data.get("name")}</li>
                    <li><strong>Email:</strong> {session.contact_data.get("email_address")}</li>
                    <li><strong>Address:</strong> {_format_address_preview(session.contact_data.get("address"))}</li>
                </ul>
            </div>
            
            <div class="button-container">
                <button class="btn btn-primary btn-lg"
                        hx-post="/contact/submit-to-xero"
                        hx-vals='{{"session_id": "{session_id}"}}'
                        hx-target="#workflow-content"
                        hx-swap="innerHTML">
                    <span class="btn-text">Create Contact in Xero</span>
                    <span class="spinner" style="display: none;">Submitting...</span>
                </button>
            </div>
        </div>
        '''

        return HTMLResponse(content=html_content)

    except Exception as e:
        logger.error(f"Error proceeding to submit: {str(e)}")
        return HTMLResponse(
            content=f'<div class="error">Error: {str(e)}</div>',
            status_code=500,
        )


@router.post("/submit-to-xero", response_model=None)
@limiter.limit("5/minute")
async def submit_to_xero(
    request: Request,
    session_id: str = Form(...),
):
    """Submit the contact to Xero."""
    is_mobile = wants_json(request)

    try:
        # Validate session
        validation_result = validate_session_id(session_id)
        if not validation_result["is_valid"]:
            if is_mobile:
                return JSONResponse(
                    content=json_error("SESSION_EXPIRED", "Session expired. Please start over."),
                    status_code=400,
                )
            return HTMLResponse(
                content='<div class="error">Session expired. Please start over.</div>',
                status_code=400,
            )

        # Get session
        session = get_contact_session(session_id)

        # Convert to ContactCreate model
        contact_model = session.to_contact_create()
        if not contact_model:
            if is_mobile:
                return JSONResponse(
                    content=json_error("INVALID_DATA", "Invalid contact data"),
                    status_code=400,
                )
            return HTMLResponse(
                content='<div class="error">Invalid contact data</div>',
                status_code=400,
            )

        # Get Xero token (supports both mobile JWT and web session)
        xero_token_data = get_xero_token(request)

        if not xero_token_data:
            if is_mobile:
                return JSONResponse(
                    content=json_error("AUTH_REQUIRED", "Xero authentication required"),
                    status_code=401,
                )
            return HTMLResponse(
                content='<div class="error">Xero authentication required. Please reconnect to Xero.</div>',
                status_code=401,
            )

        # Extract the access token
        access_token = xero_token_data.get("access_token")
        if not access_token:
            if is_mobile:
                return JSONResponse(
                    content=json_error("INVALID_TOKEN", "Invalid Xero token"),
                    status_code=401,
                )
            return HTMLResponse(
                content='<div class="error">Invalid Xero token. Please reconnect to Xero.</div>',
                status_code=401,
            )

        # Try to get tenant ID (this will fail if token is expired)
        tenant_id = await get_xero_tenant_id(access_token)

        # If we got a None response, token might be expired - try to refresh
        if not tenant_id and xero_token_data.get("refresh_token"):
            logger.info("Token might be expired, attempting to refresh...")

            # Initialize Xero OAuth2 handler
            settings = Settings()
            xero_oauth = XeroOAuth2(settings)

            # Try to refresh the token
            new_token_response = await xero_oauth.refresh_token(
                xero_token_data.get("refresh_token")
            )

            if new_token_response:
                # Update session with new tokens
                new_token_data = new_token_response.model_dump()
                session_manager.set_session_data(request, "xero_token", new_token_data)

                # Use the new access token
                access_token = new_token_data.get("access_token")

                # Try to get tenant ID again with new token
                tenant_id = await get_xero_tenant_id(access_token)
            else:
                logger.error("Failed to refresh token")
                if is_mobile:
                    return JSONResponse(
                        content=json_error("AUTH_EXPIRED", "Authentication expired"),
                        status_code=401,
                    )
                return HTMLResponse(
                    content='<div class="error">Authentication expired. Please reconnect to Xero.</div>',
                    status_code=401,
                )

        if not tenant_id:
            if is_mobile:
                return JSONResponse(
                    content=json_error("XERO_CONNECTION_ERROR", "Could not connect to Xero"),
                    status_code=500,
                )
            return HTMLResponse(
                content='<div class="error">Could not connect to Xero. Please check your authentication.</div>',
                status_code=500,
            )

        # Create contact in Xero
        xero_contact = await create_xero_contact(
            contact_data=contact_model,
            access_token=access_token,
            xero_tenant_id=tenant_id,
        )

        # Check if contact creation was successful
        if not xero_contact:
            logger.error("Failed to create contact in Xero")
            if is_mobile:
                return JSONResponse(
                    content=json_error("CREATION_FAILED", "Failed to create contact in Xero"),
                    status_code=500,
                )
            return HTMLResponse(
                content=f'''
                <div class="error-section">
                    <h3>Failed to Create Contact</h3>
                    <p>Could not create the contact in Xero. Please try again.</p>

                    <div class="button-container">
                        <button class="btn btn-warning"
                                hx-post="/contact/submit-to-xero"
                                hx-vals='{{"session_id": "{session_id}"}}'
                                hx-target="#workflow-content">
                            Retry Submission
                        </button>

                        <button class="btn btn-secondary"
                                hx-post="/contact/go-to-step"
                                hx-vals='{{"session_id": "{session_id}", "step": "review"}}'
                                hx-target="#workflow-content">
                            Back to Review
                        </button>
                    </div>
                </div>
                ''',
                status_code=500,
            )

        # Update session to complete
        session.current_step = "complete"

        # Return JSON for mobile clients
        if is_mobile:
            return JSONResponse(
                content=json_success({
                    "contact_id": xero_contact.get("contact_id"),
                    "name": xero_contact.get("name"),
                    "email": xero_contact.get("email"),
                })
            )

        # Return success HTML
        html_content = f"""
        <div class="success-section">
            <div class="success-icon">
                <svg width="60" height="60" viewBox="0 0 60 60" fill="none">
                    <circle cx="30" cy="30" r="30" fill="#28a745"/>
                    <path d="M20 30l8 8 16-16" stroke="white" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
            </div>

            <h2>Contact Created Successfully!</h2>

            <div class="contact-summary">
                <p><strong>Contact ID:</strong> {xero_contact.get("contact_id", "N/A")}</p>
                <p><strong>Name:</strong> {xero_contact.get("name", "N/A")}</p>
                <p><strong>Email:</strong> {xero_contact.get("email", "N/A")}</p>
            </div>

            <div class="button-container">
                <button class="btn btn-primary"
                        onclick="window.location.href='/contact/new'">
                    Create Another Contact
                </button>

                <button class="btn btn-secondary"
                        onclick="window.location.href='/'">
                    Back to Dashboard
                </button>
            </div>
        </div>
        """

        return HTMLResponse(content=html_content)

    except Exception as e:
        logger.error(f"Error submitting to Xero: {str(e)}")

        if is_mobile:
            return JSONResponse(
                content=json_error("SUBMISSION_ERROR", str(e)),
                status_code=500,
            )

        # Return error with retry option
        error_html = f'''
        <div class="error-section">
            <h3>Failed to Create Contact</h3>
            <p>Error: {str(e)}</p>

            <div class="button-container">
                <button class="btn btn-warning"
                        hx-post="/contact/submit-to-xero"
                        hx-vals='{{"session_id": "{session_id}"}}'
                        hx-target="#workflow-content">
                    Retry Submission
                </button>

                <button class="btn btn-secondary"
                        hx-post="/contact/go-to-step"
                        hx-vals='{{"session_id": "{session_id}", "step": "review"}}'
                        hx-target="#workflow-content">
                    Back to Review
                </button>
            </div>
        </div>
        '''

        return HTMLResponse(content=error_html, status_code=500)


@router.post("/complete")
async def complete_contact_workflow(
    request: Request,
    session_id: str = Form(...),
) -> HTMLResponse:
    """Complete the workflow and clean up."""

    try:
        session = get_contact_session(session_id)

        # Mark as complete
        session.current_step = "complete"

        # Return completion HTML
        html_content = """
        <div class="completion-section">
            <h2>Workflow Complete</h2>
            <p>Thank you for using the contact creation workflow!</p>
            
            <div class="button-container">
                <button class="btn btn-primary"
                        onclick="window.location.href='/contact/new'">
                    Create Another Contact
                </button>
                
                <button class="btn btn-secondary"
                        onclick="window.location.href='/'">
                    Return to Home
                </button>
            </div>
        </div>
        """

        return HTMLResponse(content=html_content)

    except Exception as e:
        logger.error(f"Error completing workflow: {str(e)}")
        return HTMLResponse(
            content=f'<div class="error">Error: {str(e)}</div>',
            status_code=500,
        )


def _format_address_preview(address_data) -> str:
    """Format address for preview display."""

    if not address_data:
        return "No address provided"

    parts = []
    if address_data.get("AddressLine1"):
        parts.append(address_data["AddressLine1"])
    if address_data.get("City"):
        parts.append(address_data["City"])
    if address_data.get("PostalCode"):
        parts.append(address_data["PostalCode"])
    if address_data.get("Country"):
        parts.append(address_data["Country"])

    return ", ".join(parts) if parts else "No address provided"
