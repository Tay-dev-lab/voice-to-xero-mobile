"""
Workflow management routes for contact workflow.
Handles workflow initialization, navigation, and state management.
"""

import json
import logging

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from app.api.common.response_negotiator import dual_response, json_error, json_success, wants_json
from app.api.contact_workflow.session_store import (
    cleanup_expired_sessions,
    get_contact_session,
)
from app.api.contact_workflow.validators import validate_session_id

from .auth_utils import check_auth_status
from .shared_utils import get_step_title, limiter, templates
from .template_renderers import render_review_step, render_step_with_state, render_submit_step

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/new", response_model=None)
async def new_contact_workflow(request: Request):
    """Initialize and display the contact workflow page."""

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
        session = get_contact_session(session_id)

        # Check for step parameter to navigate to
        step = request.query_params.get("step")
        if step and (step in session.get_completed_steps() or step == session.current_step):
            session.current_step = step
    else:
        # Create a new workflow session
        session = get_contact_session()

    # Return JSON for mobile clients
    if wants_json(request):
        return JSONResponse(
            content=json_success({
                "session_id": session.session_id,
                "current_step": session.current_step,
                "step_prompt": session.get_step_prompt(),
                "completed_steps": session.get_completed_steps(),
                "workflow_data": session.contact_data,
            })
        )

    # Get CSRF token from session manager
    csrf_token = ""
    if hasattr(request.app.state, "session_manager"):
        csrf_token = request.app.state.session_manager.get_or_create_csrf_token(request)

    return templates.TemplateResponse(
        "contact_workflow.html",
        {
            "request": request,
            "session_id": session.session_id,
            "current_step": session.current_step,
            "step_prompt": session.get_step_prompt(),
            "contact_data": session.contact_data,
            "csrf_token": csrf_token,
        },
    )


@router.post("/start")
async def start_contact_workflow(request: Request, session_id: str = Form(None)) -> HTMLResponse:
    """Start the contact workflow using the existing session."""

    try:
        session = get_contact_session(session_id)

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
              hx-post="/contact/step"
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

    try:
        validation_result = validate_session_id(session_id)
        if not validation_result["is_valid"]:
            if wants_json(request):
                return JSONResponse(
                    content=json_error("SESSION_EXPIRED", "Session invalid or expired"),
                    status_code=400,
                )
            return HTMLResponse(
                content='<div class="error">Session invalid or expired.</div>',
                status_code=400,
            )

        session = get_contact_session(session_id)

        workflow_steps = session.get_workflow_steps()
        if step not in workflow_steps:
            if wants_json(request):
                return JSONResponse(
                    content=json_error("INVALID_STEP", f"Invalid step: {step}"),
                    status_code=400,
                )
            return HTMLResponse(
                content=f'<div class="error">Invalid step: {step}</div>',
                status_code=400,
            )

        completed_steps = session.get_completed_steps()
        if step in completed_steps or step == session.current_step:
            session.current_step = step

            # Return JSON for mobile clients
            if wants_json(request):
                return JSONResponse(
                    content=json_success({
                        "current_step": session.current_step,
                        "step_prompt": session.get_step_prompt(),
                        "completed_steps": session.get_completed_steps(),
                        "workflow_data": session.contact_data,
                    })
                )

            # Render proper interface based on target step
            if step == "review":
                # Don't mark review as completed until user confirms
                html_content = render_review_step(session)
                return HTMLResponse(content=html_content)
            elif step == "final_submit":
                html_content = render_submit_step(session)
                return HTMLResponse(content=html_content)
            elif step in ["name", "email", "address"]:
                # For data collection steps, render the voice recorder interface with state
                html_content = render_step_with_state(session, step)
                return HTMLResponse(content=html_content)
            else:
                # For other steps (welcome, complete), redirect to the workflow interface
                return HTMLResponse(
                    content=f"""
                    <script>
                        window.location.href = '/contact/new?session_id={session_id}&step={step}';
                    </script>
                    <div>Redirecting to {step} step...</div>
                    """
                )
        else:
            if wants_json(request):
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
        if wants_json(request):
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
        session = get_contact_session(session_id)
        session.reset()

        return HTMLResponse(
            content=f'''
        <div class="workflow-reset">
            <h2>Workflow Reset</h2>
            <p>Let's start fresh! Click the button below to begin.</p>
            <button 
                class="btn btn-primary"
                hx-post="/contact/start"
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
        session = get_contact_session(session_id)
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
