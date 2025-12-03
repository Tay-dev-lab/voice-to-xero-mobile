"""
Submission routes for invoice workflow.
Handles Xero submission and workflow completion.
"""

import logging

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse

from app.api.auth import Settings, XeroOAuth2
from app.api.common import get_xero_token
from app.api.common.response_negotiator import json_error, json_success, wants_json
from app.api.invoice_workflow.session_store import get_invoice_session
from app.api.invoice_workflow.validators import validate_session_id
from app.api.invoice_workflow.xero_service import create_xero_invoice, get_xero_tenant_id

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
        session = get_invoice_session(session_id)

        # Verify all required data is present
        if not session.to_invoice_create():
            return HTMLResponse(
                content='<div class="error">Missing required invoice information</div>',
                status_code=400,
            )

        # Mark review step as completed now that user has confirmed
        if "review" not in session.completed_steps:
            session.completed_steps.append("review")

        # Advance to final_submit step
        session.current_step = "final_submit"

        # Use the template renderer for consistent UI
        from .template_renderers import render_submit_step
        html_content = render_submit_step(session)
        
        # Add script to update step indicators with review marked as completed
        indicator_script = """
        <script>
            (function() {
                // Update step indicators to show review as completed
                const steps = document.querySelectorAll('.steps-progress .step');
                const completedSteps = ['contact_name', 'due_date', 'line_item', 'review'];
                
                steps.forEach(s => {
                    s.classList.remove('active', 'completed');
                    
                    const stepName = s.dataset.step;
                    if (completedSteps.includes(stepName)) {
                        s.classList.add('completed');
                    }
                });
                
                // Update global state
                window.currentStep = 'final_submit';
                window.completedSteps = ['contact_name', 'due_date', 'line_item', 'review'];
            })();
        </script>
        """
        
        # Combine the rendered content with the indicator update script
        full_html = html_content + indicator_script

        return HTMLResponse(content=full_html)

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
    """Submit the invoice to Xero."""
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
        session = get_invoice_session(session_id)

        # Validate required invoice data is present
        if not session.to_invoice_create():
            missing = []
            if not session.invoice_data.get("contact_name"):
                missing.append("contact name")
            if not session.invoice_data.get("due_date"):
                missing.append("due date")
            if not session.invoice_data.get("line_items"):
                missing.append("line items")
            error_msg = f"Missing required data: {', '.join(missing)}" if missing else "Invalid invoice data"

            if is_mobile:
                return JSONResponse(
                    content=json_error("INVALID_DATA", error_msg),
                    status_code=400,
                )
            return HTMLResponse(
                content=f'<div class="error">{error_msg}</div>',
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
                content='<div class="error">Xero authentication required. Please reconnect.</div>',
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
                content='<div class="error">Could not connect to Xero. Please check auth.</div>',
                status_code=500,
            )

        # Create invoice in Xero
        # Pass the session data directly - function will find/create contact and create invoice
        xero_invoice = await create_xero_invoice(
            contact_name=session.invoice_data["contact_name"],
            due_date=session.invoice_data["due_date"],
            line_items=session.invoice_data["line_items"],
            access_token=access_token,
            xero_tenant_id=tenant_id,
            contact_id=session.invoice_data.get("contact_id"),  # Use if selected from dropdown
            send_email=True,  # Send email after creation
        )

        # Check if invoice creation was successful
        if not xero_invoice:
            logger.error("Failed to create invoice in Xero")
            if is_mobile:
                return JSONResponse(
                    content=json_error("CREATION_FAILED", "Failed to create invoice in Xero"),
                    status_code=500,
                )
            return HTMLResponse(
                content=f'''
                <div class="error-section">
                    <h3>Failed to Create Invoice</h3>
                    <p>Could not create the invoice in Xero. Please try again.</p>

                    <div class="button-container">
                        <button class="btn btn-warning"
                                hx-post="/invoice/submit-to-xero"
                                hx-vals='{{"session_id": "{session_id}"}}'
                                hx-target="#workflow-content">
                            Retry Submission
                        </button>

                        <button class="btn btn-secondary"
                                hx-post="/invoice/go-to-step"
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
                    "invoice_id": xero_invoice.get("invoice_id"),
                    "invoice_number": xero_invoice.get("invoice_number"),
                    "contact_name": xero_invoice.get("contact_name"),
                    "total": xero_invoice.get("total"),
                    "status": xero_invoice.get("status"),
                    "online_invoice_url": xero_invoice.get("online_invoice_url"),
                    "email_sent": xero_invoice.get("email_sent", False),
                    "email_error": xero_invoice.get("email_error"),
                })
            )

        # Build email status message
        email_status = ""
        if xero_invoice.get("email_sent"):
            email_status = f"""
            <p class="email-success">
                <svg width="16" height="16" viewBox="0 0 16 16" fill="#28a745">
                    <path d="M8 0a8 8 0 1 0 8 8A8 8 0 0 0 8 0zm3.78 5.72L7.06 10.44a.75.75 0 0 1-1.06 0L4.22 8.66a.75.75 0 0 1 1.06-1.06l1.22 1.22 4.19-4.19a.75.75 0 0 1 1.06 1.06z"/>
                </svg>
                Email sent to {xero_invoice.get("contact_name", "contact")}
            </p>
            """
        elif xero_invoice.get("email_error"):
            email_status = f"""
            <p class="email-warning">
                <svg width="16" height="16" viewBox="0 0 16 16" fill="#ffc107">
                    <path d="M8 1a7 7 0 1 0 7 7A7 7 0 0 0 8 1zm0 11a1 1 0 1 1 1-1 1 1 0 0 1-1 1zm1-3H7V4h2z"/>
                </svg>
                Email not sent: {xero_invoice.get("email_error")}
            </p>
            """

        # Build online invoice link
        online_url = xero_invoice.get("online_invoice_url", "")
        online_link = ""
        if online_url:
            online_link = f"""
            <a href="{online_url}" target="_blank" class="btn btn-outline">
                <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
                    <path d="M8.636 3.5a.5.5 0 0 0-.5-.5H1.5A1.5 1.5 0 0 0 0 4.5v10A1.5 1.5 0 0 0 1.5 16h10a1.5 1.5 0 0 0 1.5-1.5V7.864a.5.5 0 0 0-1 0V14.5a.5.5 0 0 1-.5.5h-10a.5.5 0 0 1-.5-.5v-10a.5.5 0 0 1 .5-.5h6.636a.5.5 0 0 0 .5-.5z"/>
                    <path d="M16 .5a.5.5 0 0 0-.5-.5h-5a.5.5 0 0 0 0 1h3.793L6.146 9.146a.5.5 0 1 0 .708.708L15 1.707V5.5a.5.5 0 0 0 1 0v-5z"/>
                </svg>
                View Invoice Online
            </a>
            """

        # Return success HTML
        html_content = f"""
        <div class="success-section">
            <div class="success-icon">
                <svg width="60" height="60" viewBox="0 0 60 60" fill="none">
                    <circle cx="30" cy="30" r="30" fill="#28a745"/>
                    <path d="M20 30l8 8 16-16" stroke="white" stroke-width="3"/>
                </svg>
            </div>

            <h2>Invoice Created Successfully!</h2>

            <div class="invoice-summary">
                <p><strong>Invoice Number:</strong> {xero_invoice.get("invoice_number", "N/A")}</p>
                <p><strong>Contact:</strong> {xero_invoice.get("contact_name", "N/A")}</p>
                <p><strong>Total:</strong> £{xero_invoice.get("total", 0):.2f}</p>
                <p><strong>Status:</strong> {xero_invoice.get("status", "N/A")}</p>
                {email_status}
            </div>

            <div class="button-container">
                {online_link}

                <button class="btn btn-primary"
                        onclick="window.location.href='/invoice/new'">
                    Create Another Invoice
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
            <h3>Failed to Create Invoice</h3>
            <p>Error: {str(e)}</p>

            <div class="button-container">
                <button class="btn btn-warning"
                        hx-post="/invoice/submit-to-xero"
                        hx-vals='{{"session_id": "{session_id}"}}'
                        hx-target="#workflow-content">
                    Retry Submission
                </button>

                <button class="btn btn-secondary"
                        hx-post="/invoice/go-to-step"
                        hx-vals='{{"session_id": "{session_id}", "step": "review"}}'
                        hx-target="#workflow-content">
                    Back to Review
                </button>
            </div>
        </div>
        '''

        return HTMLResponse(content=error_html, status_code=500)


@router.post("/complete")
async def complete_invoice_workflow(
    request: Request,
    session_id: str = Form(...),
) -> HTMLResponse:
    """Complete the workflow and clean up."""

    try:
        session = get_invoice_session(session_id)

        # Mark as complete
        session.current_step = "complete"

        # Return completion HTML
        html_content = """
        <div class="completion-section">
            <h2>Workflow Complete</h2>
            <p>Thank you for using the invoice creation workflow!</p>
            
            <div class="button-container">
                <button class="btn btn-primary"
                        onclick="window.location.href='/invoice/new'">
                    Create Another Invoice
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
