"""
Workflow management routes for invoice workflow.
Handles workflow initialization, navigation, and state management.
"""

import json
import logging

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from app.api.common.response_negotiator import json_error, json_success, wants_json
from app.api.invoice_workflow.session_store import (
    cleanup_expired_sessions,
    get_invoice_session,
)
from app.api.invoice_workflow.validators import validate_session_id
from app.api.invoice_workflow.xero_service import get_xero_contacts
from app.api.common import get_xero_token

from .auth_utils import check_auth_status
from .shared_utils import get_step_title, limiter, templates
from .template_renderers import (
    render_invoice_step_with_state,
    render_review_step,
    render_step_with_state,
    render_submit_step,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/new", response_model=None)
async def new_invoice_workflow(request: Request):
    """Initialize and display the invoice workflow page."""

    # Check authentication status
    is_auth, error_msg = check_auth_status(request)
    if not is_auth:
        if wants_json(request):
            return JSONResponse(
                content=json_error("AUTH_REQUIRED", "Authentication required"),
                status_code=401,
            )
        return RedirectResponse(url="/?error=auth_required", status_code=302)

    # Clean up expired sessions periodically
    cleanup_expired_sessions()

    # Check for existing session_id in query params
    session_id = request.query_params.get("session_id")
    if session_id:
        # Load existing session
        session = get_invoice_session(session_id)

        # Check for step parameter to navigate to
        step = request.query_params.get("step")
        if step and (step in session.get_completed_steps() or step == session.current_step):
            session.current_step = step
    else:
        # Create a new workflow session
        session = get_invoice_session()

    # Return JSON for mobile clients
    if wants_json(request):
        return JSONResponse(
            content=json_success({
                "session_id": session.session_id,
                "current_step": session.current_step,
                "step_prompt": session.get_step_prompt(),
                "completed_steps": session.get_completed_steps(),
                "workflow_data": session.invoice_data,
            })
        )

    # Get CSRF token from session manager
    csrf_token = ""
    if hasattr(request.app.state, "session_manager"):
        csrf_token = request.app.state.session_manager.get_or_create_csrf_token(request)

    return templates.TemplateResponse(
        "invoice_workflow.html",
        {
            "request": request,
            "session_id": session.session_id,
            "current_step": session.current_step,
            "step_prompt": session.get_step_prompt(),
            "invoice_data": session.invoice_data,
            "csrf_token": csrf_token,
        },
    )


@router.post("/start")
async def start_invoice_workflow(request: Request, session_id: str = Form(None)) -> HTMLResponse:
    """Start the invoice workflow using the existing session."""

    try:
        session = get_invoice_session(session_id)

        if session.current_step == "welcome":
            session.advance_step()

        html_content = f'''
        <div id="step-prompt" class="prompt-section">
            <h3>{session.get_step_prompt()}</h3>
        </div>
        <div id="voice-recorder" class="recorder-section">
            <div class="button-container">
                <button id="confirm-step-btn" class="btn btn-primary btn-large" disabled>
                    Continue
                </button>
                <button id="record-button" class="record-btn">
                    <svg class="mic-icon" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"></path>
                        <path d="M19 10v2a7 7 0 0 1-14 0v-2"></path>
                        <line x1="12" y1="19" x2="12" y2="23"></line>
                        <line x1="8" y1="23" x2="16" y2="23"></line>
                    </svg>
                    <span class="btn-text">Hold to Record</span>
                </button>
            </div>
            <div class="recording-indicator" id="recording-indicator" style="display: none;">
                <span class="pulse"></span>
                <span>Recording...</span>
            </div>
        </div>
        <!-- Hidden form for HTMX submission -->
        <form id="step-form" style="display: none;"
              hx-post="/invoice/step"
              hx-target="#step-result"
              hx-swap="innerHTML">
            <input type="hidden" name="session_id" value="{session_id}">
            <input type="hidden" name="step" id="current-step" value="{session.current_step}">
            <input type="file" name="file" id="audio-file" accept="audio/*">
        </form>
        <div id="step-result" class="result-section"></div>
        <script>
            // Update global state
            window.currentStep = '{session.current_step}';
            window.sessionId = '{session_id}';
            window.hasRecorded = false;
            
            // Initialize voice recorder
            if (window.initVoiceRecorder) {{
                window.initVoiceRecorder();
            }}
            
            // Update step indicators
            const steps = document.querySelectorAll('.step');
            const completedSteps = {json.dumps(session.completed_steps if hasattr(session, "completed_steps") else [])};
            
            steps.forEach(s => {{
                s.classList.remove('active', 'completed');
                
                const stepName = s.dataset.step;
                const isCompleted = completedSteps.includes(stepName);
                const isCurrent = stepName === '{session.current_step}';
                
                if (isCurrent) {{
                    // Current step gets only active class (blue)
                    s.classList.add('active');
                }} else if (isCompleted) {{
                    // Completed steps get completed class (green)
                    s.classList.add('completed');
                }}
            }});
        </script>
        '''

        return HTMLResponse(content=html_content)

    except Exception as e:
        logger.error(f"Error starting workflow: {str(e)}")
        return HTMLResponse(
            content=f'<div class="error-message">Error: {str(e)}</div>', status_code=500
        )


@router.post("/go-to-step", response_model=None)
async def go_to_step(
    request: Request,
    step: str = Form(...),
    session_id: str = Form(...),
):
    """Navigate to a specific step in the workflow."""
    is_mobile = wants_json(request)

    try:
        validation_result = validate_session_id(session_id)
        if not validation_result["is_valid"]:
            if is_mobile:
                return JSONResponse(
                    content=json_error("SESSION_EXPIRED", "Session invalid or expired"),
                    status_code=400,
                )
            return HTMLResponse(
                content='<div class="error">Session invalid or expired.</div>',
                status_code=400,
            )

        session = get_invoice_session(session_id)

        workflow_steps = session.get_workflow_steps()
        if step not in workflow_steps:
            if is_mobile:
                return JSONResponse(
                    content=json_error("INVALID_STEP", f"Invalid step: {step}"),
                    status_code=400,
                )
            return HTMLResponse(
                content=f'<div class="error">Invalid step: {step}</div>',
                status_code=400,
            )

        completed_steps = session.get_completed_steps()

        # Special handling for line_item step - allow navigation if items exist
        can_navigate = False
        if step == "line_item" and session.invoice_data.get("line_items"):
            can_navigate = True
        elif step in completed_steps or step == session.current_step:
            can_navigate = True

        if can_navigate:
            session.current_step = step

            # Return JSON for mobile clients
            if is_mobile:
                return JSONResponse(
                    content=json_success({
                        "current_step": session.current_step,
                        "step_prompt": session.get_step_prompt(),
                        "completed_steps": session.get_completed_steps(),
                        "workflow_data": session.invoice_data,
                    })
                )

            # Render proper interface based on target step
            if step == "review":
                # Don't mark review as completed until user confirms
                html_content = render_review_step(session, session_id)
                return HTMLResponse(content=html_content)
            elif step == "final_submit":
                html_content = render_submit_step(session)
                return HTMLResponse(content=html_content)
            elif step in ["contact_name", "due_date", "line_item"]:
                # For invoice data collection steps, render the appropriate interface with state
                html_content = render_invoice_step_with_state(session, step)
                return HTMLResponse(content=html_content)
            elif step in ["name", "email", "address"]:
                # For contact workflow steps (backward compatibility)
                html_content = render_step_with_state(session, step)
                return HTMLResponse(content=html_content)
            else:
                # For other steps (welcome, complete), redirect to the workflow interface
                return HTMLResponse(
                    content=f"""
                    <script>
                        window.location.href = '/invoice/new?session_id={session_id}&step={step}';
                    </script>
                    <div>Redirecting to {step} step...</div>
                    """
                )
        else:
            if is_mobile:
                return JSONResponse(
                    content=json_error("STEP_NOT_ACCESSIBLE", f"Cannot navigate to incomplete step: {step}"),
                    status_code=400,
                )
            return HTMLResponse(
                content=f'<div class="error">Cannot navigate to incomplete step: {step}</div>',
                status_code=400,
            )

    except Exception as e:
        logger.error(f"Error navigating to step: {str(e)}")
        if is_mobile:
            return JSONResponse(
                content=json_error("NAVIGATION_ERROR", str(e)),
                status_code=500,
            )
        return HTMLResponse(
            content=f'<div class="error">Error: {str(e)}</div>',
            status_code=500,
        )


@router.post("/reset")
async def reset_workflow(
    request: Request,
    session_id: str = Form(...),
) -> HTMLResponse:
    """Reset the workflow to start over."""

    try:
        session = get_invoice_session(session_id)
        session.reset()

        return HTMLResponse(
            content=f'''
        <div class="workflow-reset">
            <h2>Workflow Reset</h2>
            <p>Let's start fresh! Click the button below to begin.</p>
            <button 
                class="btn btn-primary"
                hx-post="/invoice/start"
                hx-vals='{{"session_id": "{session_id}"}}'
                hx-target="#workflow-container"
                hx-swap="innerHTML"
            >
                Start New Contact
            </button>
        </div>
        '''
        )

    except Exception as e:
        logger.error(f"Error resetting workflow: {str(e)}")
        return HTMLResponse(
            content=f'<div class="error">Error: {str(e)}</div>',
            status_code=500,
        )


@router.get("/step-prompt")
@limiter.limit("30/minute")
async def get_step_prompt(
    request: Request,
    session_id: str,
    step: str | None = None,
) -> JSONResponse:
    """Get the prompt for a specific step."""

    try:
        session = get_invoice_session(session_id)
        target_step = step or session.current_step

        prompts = session.STEP_PROMPTS if hasattr(session, "STEP_PROMPTS") else {}
        prompt = prompts.get(target_step, "Unknown step")

        return JSONResponse(
            {
                "step": target_step,
                "prompt": prompt,
                "title": get_step_title(target_step),
            }
        )

    except Exception as e:
        logger.error(f"Error getting step prompt: {str(e)}")
        return JSONResponse(
            {"error": str(e)},
            status_code=500,
        )


@router.get("/contacts")
@limiter.limit("10/minute")
async def get_contacts(request: Request) -> JSONResponse:
    """
    Get list of customer contacts from Xero for dropdown selection.

    Returns list of contacts with contact_id, name, and email.
    """
    try:
        # Check authentication
        is_auth, error_msg = check_auth_status(request)
        if not is_auth:
            return JSONResponse(
                content=json_error("AUTH_REQUIRED", "Authentication required"),
                status_code=401,
            )

        # Get Xero token
        xero_token_data = get_xero_token(request)
        if not xero_token_data:
            return JSONResponse(
                content=json_error("AUTH_REQUIRED", "Xero authentication required"),
                status_code=401,
            )

        access_token = xero_token_data.get("access_token")
        if not access_token:
            return JSONResponse(
                content=json_error("INVALID_TOKEN", "Invalid Xero token"),
                status_code=401,
            )

        # Get tenant ID
        from app.api.invoice_workflow.xero_service import get_xero_tenant_id
        tenant_id = await get_xero_tenant_id(access_token)
        if not tenant_id:
            return JSONResponse(
                content=json_error("XERO_ERROR", "Could not connect to Xero"),
                status_code=500,
            )

        # Fetch contacts from Xero
        contacts = await get_xero_contacts(access_token, tenant_id)
        if contacts is None:
            return JSONResponse(
                content=json_error("FETCH_ERROR", "Failed to fetch contacts from Xero"),
                status_code=500,
            )

        return JSONResponse(content=json_success({"contacts": contacts}))

    except Exception as e:
        logger.error(f"Error fetching contacts: {str(e)}")
        return JSONResponse(
            content=json_error("SERVER_ERROR", str(e)),
            status_code=500,
        )


@router.post("/confirm-line-item")
async def confirm_line_item(
    request: Request,
    session_id: str = Form(...),
) -> HTMLResponse:
    """Confirm current line item and show add/review options."""

    try:
        session = get_invoice_session(session_id)

        # Move current line item to confirmed list
        if session.invoice_data.get("current_line_item"):
            session.add_line_item(session.invoice_data["current_line_item"])

        # Update step to add_or_review
        session.current_step = "add_or_review"

        # Render line items summary
        line_items_html = ""
        for idx, item in enumerate(session.invoice_data["line_items"], 1):
            line_items_html += f"""
            <div class="line-item-row">
                <span class="item-number">#{idx}</span>
                <span class="item-description">{item["description"]}</span>
                <span class="item-quantity">{item["quantity"]} × £{item["unit_price"]:.2f}</span>
                <span class="item-vat">{item["vat_rate"].replace("_", " ").title()}</span>
            </div>
            """

        # Render add or review buttons
        html = f'''
        <div class="line-item-confirmed">
            <div class="success-message">
                <svg class="checkmark" width="20" height="20" viewBox="0 0 20 20" fill="currentColor">
                    <path d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"/>
                </svg>
                Line item {session.line_item_count} added successfully
            </div>
            
            <div class="line-items-summary">
                <h4>Invoice Items ({session.line_item_count}/10)</h4>
                {line_items_html}
            </div>
            
            <div class="action-buttons">
                {"<button class='btn btn-secondary' hx-post='/invoice/add-another-item' hx-vals='{{\"session_id\": \"" + session_id + "\"}}' hx-target='#workflow-content' hx-swap='innerHTML'>Add Another Item</button>" if session.line_item_count < 10 else ""}
                
                <button class="btn btn-primary"
                        hx-post="/invoice/proceed-to-review"
                        hx-vals='{{"session_id": "{session_id}"}}'
                        hx-target="#workflow-content"
                        hx-swap="innerHTML">
                    Review Invoice
                </button>
            </div>
        </div>
        
        <script>
            // Update step indicators
            const steps = document.querySelectorAll('.step');
            steps.forEach(s => {{
                s.classList.remove('active');
                if (s.dataset.step === 'line_item') {{
                    s.classList.add('completed');
                }}
            }});
        </script>
        '''

        return HTMLResponse(content=html)

    except Exception as e:
        logger.error(f"Error confirming line item: {str(e)}")
        return HTMLResponse(
            content=f'<div class="error">Error: {str(e)}</div>',
            status_code=500,
        )


@router.post("/add-another-item")
async def add_another_item(
    request: Request,
    session_id: str = Form(...),
) -> HTMLResponse:
    """Reset to line_item step for adding another item."""

    try:
        session = get_invoice_session(session_id)
        
        # Save the current line item before resetting for a new one
        if session.invoice_data.get("current_line_item"):
            session.add_line_item(session.invoice_data["current_line_item"])
            logger.info(f"Saved line item before adding another. Total items: {session.line_item_count}")
        
        session.current_step = "line_item"

        # Render line item collection UI with existing items summary
        line_items_html = ""
        if session.invoice_data["line_items"]:
            line_items_html = f"""
            <div class="existing-items-summary">
                <h5>Items added so far ({session.line_item_count}/10):</h5>
                """
            for idx, item in enumerate(session.invoice_data["line_items"], 1):
                line_items_html += f"""
                <div class="mini-item">
                    #{idx}: {item["description"]} - {item["quantity"]} × £{item["unit_price"]:.2f}
                </div>
                """
            line_items_html += "</div>"

        html_content = f'''
        <div id="step-prompt" class="prompt-section">
            <h3>{session.get_step_prompt()}</h3>
            <small class="help-text">Describe the item, quantity, price, and VAT rate (standard, reduced, zero-rated, or exempt)</small>
        </div>
        
        {line_items_html}
        
        <div id="voice-recorder" class="recorder-section">
            <div class="button-container">
                <button id="confirm-step-btn" class="btn btn-primary btn-large" disabled>
                    Continue
                </button>
                <button id="record-button" class="record-btn">
                    <svg class="mic-icon" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"></path>
                        <path d="M19 10v2a7 7 0 0 1-14 0v-2"></path>
                        <line x1="12" y1="19" x2="12" y2="23"></line>
                        <line x1="8" y1="23" x2="16" y2="23"></line>
                    </svg>
                    <span class="btn-text">Hold to Record</span>
                </button>
            </div>
            <div class="recording-indicator" id="recording-indicator" style="display: none;">
                <span class="pulse"></span>
                <span>Recording...</span>
            </div>
        </div>
        
        <!-- Hidden form for HTMX submission -->
        <form id="step-form" style="display: none;"
              hx-post="/invoice/step"
              hx-target="#step-result"
              hx-swap="innerHTML">
            <input type="hidden" name="session_id" value="{session_id}">
            <input type="hidden" name="step" id="current-step" value="line_item">
            <input type="file" name="file" id="audio-file" accept="audio/*">
        </form>
        
        <div id="step-result" class="result-section"></div>
        
        <script>
            // Reset recording state
            window.currentStep = 'line_item';
            window.hasRecorded = false;
            
            // Re-initialize voice recorder
            if (window.initVoiceRecorder) {{
                window.initVoiceRecorder();
            }}
        </script>
        '''

        return HTMLResponse(content=html_content)

    except Exception as e:
        logger.error(f"Error adding another item: {str(e)}")
        return HTMLResponse(
            content=f'<div class="error">Error: {str(e)}</div>',
            status_code=500,
        )


@router.post("/proceed-to-review")
async def proceed_to_review(
    request: Request,
    session_id: str = Form(...),
) -> HTMLResponse:
    """Proceed to review step with all invoice details."""

    try:
        session = get_invoice_session(session_id)
        
        # Save the current line item if it exists before proceeding to review
        if session.invoice_data.get("current_line_item"):
            session.add_line_item(session.invoice_data["current_line_item"])
            logger.info(f"Saved pending line item before review. Total items: {session.line_item_count}")
        
        session.current_step = "review"

        # Mark line_item_confirm as completed
        if "line_item_confirm" not in session.completed_steps:
            session.completed_steps.append("line_item_confirm")

        # Call the review step renderer
        html_content = render_review_step(session, session_id)
        return HTMLResponse(content=html_content)

    except Exception as e:
        logger.error(f"Error proceeding to review: {str(e)}")
        return HTMLResponse(
            content=f'<div class="error">Error: {str(e)}</div>',
            status_code=500,
        )
