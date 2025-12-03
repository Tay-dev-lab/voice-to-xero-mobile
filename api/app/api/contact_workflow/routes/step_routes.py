"""
Step processing routes for contact workflow.
Handles voice input processing, step confirmation, and field updates.
"""

import json
import logging

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse

from app.api.common import get_openai_api_key
from app.api.common.response_negotiator import json_error, json_success, wants_json
from app.api.contact_workflow.models import StepValidationError
from app.api.contact_workflow.session_store import get_contact_session
from app.api.contact_workflow.step_handlers import process_voice_step
from app.api.contact_workflow.validators import validate_session_id

from .shared_utils import generate_step_result_html, limiter
from .template_renderers import render_review_step, render_submit_step

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/step", response_model=None)
@limiter.limit("10/minute")
async def process_contact_step(
    request: Request,
    audio_file: UploadFile = File(...),
    step: str = Form(...),
    session_id: str = Form(...),
):
    """Process voice input for a workflow step."""

    logger.info(f"Processing step {step} for session {session_id}")
    is_mobile = wants_json(request)

    try:
        # Validate CSRF token (skip for mobile - uses JWT auth)
        if not is_mobile:
            session_manager = request.app.state.session_manager
            csrf_token = request.headers.get("X-CSRF-Token")
            if not csrf_token or not session_manager.validate_csrf_token(request, csrf_token):
                return HTMLResponse(
                    content='<div class="error">Invalid security token. Please refresh the page.</div>',
                    status_code=403,
                )

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

        # Get OpenAI API key (supports both mobile JWT and web session)
        api_key = get_openai_api_key(request)

        if not api_key:
            if is_mobile:
                return JSONResponse(
                    content=json_error("API_KEY_MISSING", "OpenAI API key not configured"),
                    status_code=400,
                )
            return HTMLResponse(
                content='<div class="error">OpenAI API key not configured</div>',
                status_code=400,
            )

        # Process the voice input for the specific step
        transcript, parsed_result = await process_voice_step(
            step=step,
            audio_file=audio_file,
            openai_api_key=api_key,
        )

        # Store the result in session
        session.store_step_result(step, parsed_result, transcript)

        # Return JSON for mobile clients
        if is_mobile:
            # Convert Pydantic model to dict for JSON serialization
            # Use mode='json' to ensure date/datetime objects are converted to strings
            parsed_data = parsed_result.model_dump(mode='json') if hasattr(parsed_result, 'model_dump') else parsed_result
            return JSONResponse(
                content=json_success({
                    "step": step,
                    "transcript": transcript,
                    "parsed_data": parsed_data,
                    "requires_confirmation": True,
                    "session_id": session_id,
                    "completed_steps": session.get_completed_steps(),
                })
            )

        # Generate HTML response
        html_content = generate_step_result_html(step, parsed_result, transcript, session_id)

        return HTMLResponse(content=html_content)

    except StepValidationError as e:
        logger.warning(f"Validation error in step {step}: {str(e)}")
        if is_mobile:
            return JSONResponse(
                content=json_error("VALIDATION_ERROR", str(e)),
                status_code=400,
            )
        error_html = f"""
        <div class="error-message">
            <p>{str(e)}</p>
            <button onclick="retryStep('{step}', '{session_id}')">Try Again</button>
        </div>
        """
        return HTMLResponse(content=error_html, status_code=400)

    except Exception as e:
        logger.error(f"Error processing step {step}: {str(e)}")
        if is_mobile:
            return JSONResponse(
                content=json_error("PROCESSING_ERROR", str(e)),
                status_code=500,
            )
        return HTMLResponse(
            content=f'<div class="error">Error: {str(e)}</div>',
            status_code=500,
        )


@router.post("/confirm-step", response_model=None)
async def confirm_step(
    request: Request,
    step: str = Form(None),
    session_id: str = Form(...),
):
    """Confirm step data and advance to next step."""
    is_mobile = wants_json(request)

    try:
        session = get_contact_session(session_id)

        # Get current step if not provided
        current_step = step or session.current_step

        # Mark current step as completed (using the data already stored)
        if current_step not in session.completed_steps:
            session.completed_steps.append(current_step)

        # Advance to next step
        next_step = session.advance_step()

        # Return JSON for mobile clients
        if is_mobile:
            return JSONResponse(
                content=json_success({
                    "current_step": next_step,
                    "step_prompt": session.get_step_prompt(),
                    "completed_steps": session.get_completed_steps(),
                    "workflow_data": session.contact_data,
                })
            )

        # Return appropriate interface based on next step
        if next_step == "review":
            # Don't mark review as completed until user confirms
            html_content = render_review_step(session)
        elif next_step == "final_submit":
            html_content = render_submit_step(session)
        else:
            # Render voice input interface for next step
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
                  hx-post="/contact/step"
                  hx-target="#step-result"
                  hx-swap="innerHTML">
                <input type="hidden" name="session_id" value="{session_id}">
                <input type="hidden" name="step" id="current-step" value="{next_step}">
                <input type="file" name="file" id="audio-file" accept="audio/*">
            </form>
            <div id="step-result" class="result-section"></div>
            <script>
                // Update global state
                window.currentStep = '{next_step}';
                window.sessionId = '{session_id}';
                window.hasRecorded = false;

                // Reinitialize voice recorder
                if (window.initVoiceRecorder) {{
                    window.initVoiceRecorder();
                }}

                // Update step indicators immediately
                (function() {{
                    const steps = document.querySelectorAll('.steps-progress .step');
                    const completedSteps = {json.dumps(session.completed_steps if hasattr(session, "completed_steps") else [])};

                    steps.forEach(s => {{
                        // Remove all classes first
                        s.classList.remove('active', 'completed');

                        const stepName = s.dataset.step;
                        const isCompleted = completedSteps.includes(stepName);
                        const isCurrent = stepName === '{next_step}';

                        if (isCurrent) {{
                            // Current step gets only active class (blue)
                            s.classList.add('active');
                        }} else if (isCompleted) {{
                            // Completed steps get completed class (green)
                            s.classList.add('completed');
                        }}
                    }});
                    console.log('Step indicators updated: steps before {next_step} completed, {next_step} active');

                    // Update step clickability after setting visual states
                    if (window.updateStepClickability) {{
                        window.updateStepClickability();
                    }}
                }})();
            </script>
            '''

        return HTMLResponse(content=html_content)

    except Exception as e:
        logger.error(f"Error confirming step: {str(e)}")
        if is_mobile:
            return JSONResponse(
                content=json_error("CONFIRMATION_ERROR", str(e)),
                status_code=500,
            )
        return HTMLResponse(
            content=f'<div class="error">Error: {str(e)}</div>',
            status_code=500,
        )


@router.get("/summary", response_model=None)
@limiter.limit("30/minute")
async def get_contact_summary(
    request: Request,
    session_id: str,
):
    """Get summary of contact data collected so far."""
    is_mobile = wants_json(request)

    try:
        session = get_contact_session(session_id)
        data = session.contact_data

        # Return JSON for mobile clients
        if is_mobile:
            return JSONResponse(
                content=json_success({
                    "name": data.get("name"),
                    "email_address": data.get("email_address"),
                    "address": data.get("address"),
                    "is_organization": data.get("is_organization", False),
                })
            )

        # Build the HTML summary
        html_content = '<div class="contact-summary">'
        html_content += "<h4>Contact Information</h4>"

        if data.get("name"):
            html_content += f'''
            <div class="summary-field">
                <label>Name:</label>
                <span class="editable-value" contenteditable="true" 
                      data-field="name" data-session="{session_id}">{data["name"]}</span>
                <span class="edit-icon">✎</span>
            </div>
            '''

        if data.get("email_address"):
            html_content += f'''
            <div class="summary-field">
                <label>Email:</label>
                <span class="editable-value" contenteditable="true"
                      data-field="email_address" data-session="{session_id}">{data["email_address"]}</span>
                <span class="edit-icon">✎</span>
            </div>
            '''

        if data.get("address"):
            address = data["address"]
            html_content += f'''
            <div class="summary-field">
                <label>Address:</label>
                <div class="address-block">
                    <div contenteditable="true" data-field="address_line1" data-session="{session_id}">
                        {address.get("AddressLine1", "")}
                    </div>
                    <div>
                        <span contenteditable="true" data-field="city" data-session="{session_id}">
                            {address.get("City", "")}
                        </span>,
                        <span contenteditable="true" data-field="postal_code" data-session="{session_id}">
                            {address.get("PostalCode", "")}
                        </span>
                    </div>
                    <div contenteditable="true" data-field="country" data-session="{session_id}">
                        {address.get("Country", "GB")}
                    </div>
                </div>
            </div>
            '''

        html_content += "</div>"

        # Add script for inline editing
        html_content += """
        <script>
            // Initialize editable fields
            document.querySelectorAll('[contenteditable="true"]').forEach(field => {
                field.addEventListener('blur', async function() {
                    const fieldName = this.dataset.field;
                    const sessionId = this.dataset.session;
                    const value = this.textContent.trim();
                    
                    // Save the change
                    const formData = new FormData();
                    formData.append('field_name', fieldName);
                    formData.append('field_value', value);
                    formData.append('session_id', sessionId);
                    
                    await fetch('/contact/update-field', {
                        method: 'POST',
                        body: formData
                    });
                    
                    // Show save indicator
                    this.style.backgroundColor = '#e8f5e9';
                    setTimeout(() => {
                        this.style.backgroundColor = '';
                    }, 1000);
                });
                
                field.addEventListener('focus', function() {
                    // Select all text on focus
                    const range = document.createRange();
                    range.selectNodeContents(this);
                    const sel = window.getSelection();
                    sel.removeAllRanges();
                    sel.addRange(range);
                });
            });
        </script>
        """

        return HTMLResponse(content=html_content)

    except Exception as e:
        logger.error(f"Error getting summary: {str(e)}")
        if is_mobile:
            return JSONResponse(
                content=json_error("SUMMARY_ERROR", str(e)),
                status_code=500,
            )
        return HTMLResponse(
            content='<div class="error">Error loading summary</div>',
            status_code=500,
        )


@router.post("/update-field", response_model=None)
async def update_contact_field(
    request: Request,
    field_name: str = Form(...),
    field_value: str = Form(...),
    session_id: str = Form(...),
):
    """Update a single contact field."""
    is_mobile = wants_json(request)

    try:
        # Validate session
        validation_result = validate_session_id(session_id)
        if not validation_result["is_valid"]:
            if is_mobile:
                return JSONResponse(
                    content=json_error("SESSION_EXPIRED", "Session expired"),
                    status_code=400,
                )
            return HTMLResponse(
                content='<div class="error">Session expired</div>',
                status_code=400,
            )

        # Get session and update field
        session = get_contact_session(session_id)
        session.update_field(field_name, field_value)

        # Return JSON for mobile clients
        if is_mobile:
            return JSONResponse(
                content=json_success({
                    "field": field_name,
                    "value": field_value,
                    "updated": True,
                })
            )

        # Return success message
        return HTMLResponse(content=f'<div class="success">Updated {field_name}</div>')

    except Exception as e:
        logger.error(f"Error updating field: {str(e)}")
        if is_mobile:
            return JSONResponse(
                content=json_error("UPDATE_ERROR", str(e)),
                status_code=500,
            )
        return HTMLResponse(
            content=f'<div class="error">Error: {str(e)}</div>',
            status_code=500,
        )
