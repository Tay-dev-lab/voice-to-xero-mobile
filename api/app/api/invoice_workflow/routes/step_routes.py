"""
Step processing routes for invoice workflow.
Handles voice input processing, step confirmation, and field updates.
"""

import json
import logging

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse

from app.api.common import get_openai_api_key
from app.api.common.response_negotiator import json_error, json_success, wants_json
from app.api.invoice_workflow.models import StepValidationError
from app.api.invoice_workflow.session_store import get_invoice_session
from app.api.invoice_workflow.step_handlers import process_voice_step
from app.api.invoice_workflow.validators import validate_session_id

from .shared_utils import generate_step_result_html, limiter
from .template_renderers import render_line_item_confirm, render_review_step, render_submit_step

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/step", response_model=None)
@limiter.limit("10/minute")
async def process_invoice_step(
    request: Request,
    audio_file: UploadFile = File(...),  # noqa: B008
    step: str = Form(...),  # noqa: B008
    session_id: str = Form(...),  # noqa: B008
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
                    content='<div class="error">Invalid security token. Please refresh.</div>',
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
        session = get_invoice_session(session_id)

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
                    "has_pending_item": session.has_pending_item,
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
        session = get_invoice_session(session_id)

        # Get current step if not provided
        current_step = step or session.current_step

        logger.info(f"Confirm step called for step: {current_step}, has_pending_item: {session.has_pending_item}")

        # Special handling for line_item step
        if current_step == "line_item" and session.has_pending_item:
            logger.info("Showing line item confirmation screen")
            # Return JSON for mobile - let client decide next action
            if is_mobile:
                return JSONResponse(
                    content=json_success({
                        "requires_line_item_decision": True,
                        "current_item": session.invoice_data.get("current_line_item"),
                        "existing_items": session.invoice_data.get("line_items", []),
                        "session_id": session_id,
                    })
                )
            # Show line item confirmation with Add Another / Review options
            html_content = render_line_item_confirm(session, session_id)
            return HTMLResponse(content=html_content)

        # Mark current step as completed (except line_item which is handled differently)
        if current_step != "line_item" and current_step not in session.completed_steps:
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
                    "workflow_data": session.invoice_data,
                })
            )

        # Return appropriate interface based on next step
        if next_step == "review":
            # Don't mark review as completed until user confirms
            html_content = render_review_step(session, session_id)
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
                  hx-post="/invoice/step"
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


@router.post("/confirm-line-item", response_model=None)
async def confirm_line_item(
    request: Request,
    session_id: str = Form(...),
    add_another: str = Form("false"),
):
    """Confirm line item and either add another or proceed to review."""
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

        session = get_invoice_session(session_id)

        # Save current line item to the list
        current_item = session.invoice_data.get("current_line_item")
        if current_item:
            session.add_line_item(current_item)

        if add_another.lower() == "true":
            # Prepare for next item
            session.current_step = "line_item"
            session.has_pending_item = False

            if is_mobile:
                return JSONResponse(
                    content=json_success({
                        "current_step": "line_item",
                        "step_prompt": f"Item {len(session.invoice_data['line_items']) + 1}: "
                                       "Describe the next line item",
                        "completed_steps": session.get_completed_steps(),
                        "line_items": session.invoice_data.get("line_items", []),
                        "item_count": len(session.invoice_data.get("line_items", [])),
                    })
                )

            # Return voice input interface for new line item (web)
            html_content = f'''
            <div id="step-prompt" class="prompt-section">
                <h3>Item {len(session.invoice_data["line_items"]) + 1}: Describe the next item</h3>
            </div>
            <div id="voice-recorder" class="recorder-section">
                <button id="record-button" class="record-btn">Hold to Record</button>
            </div>
            <form id="step-form" style="display: none;">
                <input type="hidden" name="session_id" value="{session_id}">
                <input type="hidden" name="step" value="line_item">
            </form>
            <div id="step-result" class="result-section"></div>
            '''
            return HTMLResponse(content=html_content)

        else:
            # Proceed to review
            if "line_item" not in session.completed_steps:
                session.completed_steps.append("line_item")
            session.current_step = "review"
            session.has_pending_item = False

            if is_mobile:
                return JSONResponse(
                    content=json_success({
                        "current_step": "review",
                        "step_prompt": session.get_step_prompt(),
                        "completed_steps": session.get_completed_steps(),
                        "workflow_data": session.invoice_data,
                    })
                )

            # Render review page (web)
            html_content = render_review_step(session, session_id)
            return HTMLResponse(content=html_content)

    except Exception as e:
        logger.error(f"Error confirming line item: {str(e)}")
        if is_mobile:
            return JSONResponse(
                content=json_error("LINE_ITEM_ERROR", str(e)),
                status_code=500,
            )
        return HTMLResponse(
            content=f'<div class="error">Error: {str(e)}</div>',
            status_code=500,
        )


@router.get("/summary", response_model=None)
@limiter.limit("30/minute")
async def get_invoice_summary(
    request: Request,
    session_id: str,
):
    """Get summary of invoice data collected so far."""
    is_mobile = wants_json(request)

    try:
        session = get_invoice_session(session_id)
        data = session.invoice_data

        # Return JSON for mobile clients
        if is_mobile:
            # Calculate totals and add line_total to each item
            all_items = data.get("line_items", [])
            if data.get("current_line_item"):
                all_items = all_items + [data["current_line_item"]]

            subtotal = 0
            vat_total = 0
            items_with_totals = []
            for item in all_items:
                qty = float(item.get("quantity", 0))
                price = float(item.get("unit_price", 0))
                item_total = qty * price
                subtotal += item_total

                vat_rate = item.get("vat_rate", "standard")
                if vat_rate == "standard":
                    vat_total += item_total * 0.20
                elif vat_rate == "reduced":
                    vat_total += item_total * 0.05

                # Add line_total to each item for frontend display
                item_with_total = {**item, "line_total": round(item_total, 2)}
                items_with_totals.append(item_with_total)

            return JSONResponse(
                content=json_success({
                    "contact_name": data.get("contact_name"),
                    "due_date": data.get("due_date"),
                    "line_items": items_with_totals,
                    "subtotal": round(subtotal, 2),
                    "vat_total": round(vat_total, 2),
                    "grand_total": round(subtotal + vat_total, 2),
                })
            )

        # Build the HTML summary
        html_content = '<div class="invoice-summary">'
        html_content += "<h4>Invoice Information</h4>"

        # Display contact name
        if data.get("contact_name"):
            html_content += f'''
            <div class="summary-field">
                <label>Contact:</label>
                <span class="editable-value" contenteditable="true" 
                      data-field="contact_name" data-session="{session_id}">{data["contact_name"]}</span>
                <span class="edit-icon">✎</span>
            </div>
            '''

        # Display due date
        if data.get("due_date"):
            html_content += f'''
            <div class="summary-field">
                <label>Due Date:</label>
                <span class="editable-value" contenteditable="true"
                      data-field="due_date" data-session="{session_id}">{data["due_date"]}</span>
                <span class="edit-icon">✎</span>
            </div>
            '''

        # Combine confirmed items and current pending item for display
        all_items = []
        if data.get("line_items"):
            all_items.extend(data["line_items"])
        if data.get("current_line_item"):
            all_items.append(data["current_line_item"])
        
        # Display line items (both confirmed and pending)
        if all_items:
            html_content += '''
            <div class="line-items-section">
                <label>Line Items:</label>
                <table class="line-items-table">
                    <thead>
                        <tr>
                            <th>Description</th>
                            <th>Qty</th>
                            <th>Price</th>
                            <th>VAT</th>
                        </tr>
                    </thead>
                    <tbody>
            '''
            
            subtotal = 0
            vat_total = 0
            
            for idx, item in enumerate(all_items):
                qty = float(item.get("quantity", 0))
                price = float(item.get("unit_price", 0))
                item_total = qty * price
                subtotal += item_total
                
                # Calculate VAT
                vat_rate = item.get("vat_rate", "standard")
                vat_amount = 0
                if vat_rate == "standard":
                    vat_amount = item_total * 0.20
                elif vat_rate == "reduced":
                    vat_amount = item_total * 0.05
                vat_total += vat_amount
                
                vat_display = vat_rate.replace("_", " ").title()
                
                html_content += f'''
                    <tr>
                        <td contenteditable="true" data-field="line_item_{idx}_description" 
                            data-session="{session_id}">{item.get("description", "")}</td>
                        <td contenteditable="true" data-field="line_item_{idx}_quantity" 
                            data-session="{session_id}">{int(qty)}</td>
                        <td contenteditable="true" data-field="line_item_{idx}_unit_price" 
                            data-session="{session_id}">£{price:.2f}</td>
                        <td>{vat_display}</td>
                    </tr>
                '''
            
            # Close table
            html_content += '''
                    </tbody>
                </table>
            '''
            
            # Add totals section below table
            grand_total = subtotal + vat_total
            html_content += f'''
                <div class="invoice-totals">
                    <div class="total-line">
                        <span>Subtotal:</span>
                        <span>£{subtotal:.2f}</span>
                    </div>
                    <div class="total-line">
                        <span>VAT:</span>
                        <span>£{vat_total:.2f}</span>
                    </div>
                    <div class="total-line grand-total">
                        <span><strong>Total:</strong></span>
                        <span><strong>£{grand_total:.2f}</strong></span>
                    </div>
                </div>
            </div>
            '''

        # Display current line item being created
        elif data.get("current_line_item"):
            item = data["current_line_item"]
            html_content += f'''
            <div class="current-line-item">
                <label>Current Line Item (not yet confirmed):</label>
                <div class="item-preview">
                    {item.get("description", "")} - 
                    {item.get("quantity", 0)} × £{item.get("unit_price", 0):.2f}
                    ({item.get("vat_rate", "standard").replace("_", " ").title()})
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
                    
                    await fetch('/invoice/update-field', {
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
async def update_invoice_field(
    request: Request,
    field_name: str = Form(...),
    field_value: str = Form(...),
    session_id: str = Form(...),
):
    """Update a single invoice field."""
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
        session = get_invoice_session(session_id)
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


@router.post("/add-another-item", response_model=None)
async def add_another_item(
    request: Request,
    session_id: str = Form(...),
):
    """Save current line item and prepare for adding another."""
    is_mobile = wants_json(request)

    try:
        session = get_invoice_session(session_id)

        # Save current line item to the list
        current_item = session.invoice_data.get("current_line_item")
        if current_item:
            session.add_line_item(current_item)

        # Stay on line_item step for new item
        session.current_step = "line_item"

        # Return JSON for mobile clients
        if is_mobile:
            return JSONResponse(
                content=json_success({
                    "current_step": "line_item",
                    "step_prompt": f"Item {len(session.invoice_data['line_items']) + 1}: Describe the next line item",
                    "completed_steps": session.get_completed_steps(),
                    "line_items": session.invoice_data.get("line_items", []),
                    "item_count": len(session.invoice_data.get("line_items", [])),
                })
            )

        # Return voice input interface for new line item
        html_content = f'''
        <div id="step-prompt" class="prompt-section">
            <h3>Item {len(session.invoice_data["line_items"]) + 1}: Please describe the next line item</h3>
        </div>
        <div id="voice-recorder" class="recorder-section">
            <button id="record-button" class="record-btn">
                <svg class="mic-icon" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"></path>
                    <path d="M19 10v2a7 7 0 0 1-14 0v-2"></path>
                    <line x1="12" y1="19" x2="12" y2="23"></line>
                    <line x1="8" y1="23" x2="16" y2="23"></line>
                </svg>
                <span class="btn-text">Hold to Record</span>
            </button>
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
        
        <div class="items-counter">
            <p>{len(session.invoice_data["line_items"])} item{"s" if len(session.invoice_data["line_items"]) != 1 else ""} added so far</p>
        </div>
        
        <script>
            // Update global state
            window.currentStep = 'line_item';
            window.sessionId = '{session_id}';
            window.hasRecorded = false;
            
            // Reinitialize voice recorder
            if (window.initVoiceRecorder) {{
                window.initVoiceRecorder();
            }}
            
            // Trigger summary update
            document.body.dispatchEvent(new CustomEvent('step-recorded'));
        </script>
        '''
        
        return HTMLResponse(content=html_content)

    except Exception as e:
        logger.error(f"Error adding another item: {str(e)}")
        if is_mobile:
            return JSONResponse(
                content=json_error("ADD_ITEM_ERROR", str(e)),
                status_code=500,
            )
        return HTMLResponse(
            content=f'<div class="error">Error: {str(e)}</div>',
            status_code=500,
        )


@router.post("/proceed-to-review", response_model=None)
async def proceed_to_review(
    request: Request,
    session_id: str = Form(...),
):
    """Save current line item and proceed to review step."""
    is_mobile = wants_json(request)

    try:
        session = get_invoice_session(session_id)

        # Save current line item if exists
        current_item = session.invoice_data.get("current_line_item")
        if current_item:
            session.add_line_item(current_item)

        # Ensure we have at least one line item
        if not session.invoice_data.get("line_items"):
            if is_mobile:
                return JSONResponse(
                    content=json_error("NO_LINE_ITEMS", "Please add at least one line item"),
                    status_code=400,
                )
            return HTMLResponse(
                content='<div class="error">Please add at least one line item</div>',
                status_code=400,
            )

        # Mark line_item as completed and move to review
        if "line_item" not in session.completed_steps:
            session.completed_steps.append("line_item")

        session.current_step = "review"

        # Return JSON for mobile clients
        if is_mobile:
            return JSONResponse(
                content=json_success({
                    "current_step": "review",
                    "completed_steps": session.get_completed_steps(),
                    "workflow_data": session.invoice_data,
                })
            )

        # Render review page
        html_content = render_review_step(session, session_id)

        return HTMLResponse(content=html_content)

    except Exception as e:
        logger.error(f"Error proceeding to review: {str(e)}")
        if is_mobile:
            return JSONResponse(
                content=json_error("REVIEW_ERROR", str(e)),
                status_code=500,
            )
        return HTMLResponse(
            content=f'<div class="error">Error: {str(e)}</div>',
            status_code=500,
        )


@router.post("/clear-line-item", response_model=None)
async def clear_line_item(
    request: Request,
    session_id: str = Form(...),
    item_index: int = Form(...),
):
    """Remove a specific line item by index."""
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

        session = get_invoice_session(session_id)

        # Remove item at index if valid
        if 0 <= item_index < len(session.invoice_data.get("line_items", [])):
            session.invoice_data["line_items"].pop(item_index)
            session.line_item_count = len(session.invoice_data["line_items"])
            logger.info(f"Cleared line item {item_index}, remaining: {session.line_item_count}")

        if is_mobile:
            return JSONResponse(
                content=json_success({
                    "success": True,
                    "item_count": session.line_item_count,
                    "line_items": session.invoice_data.get("line_items", []),
                })
            )

        return HTMLResponse(
            content=f'<div class="success">Item removed. {session.line_item_count} items remaining.</div>'
        )

    except Exception as e:
        logger.error(f"Error clearing line item: {str(e)}")
        if is_mobile:
            return JSONResponse(
                content=json_error("CLEAR_ITEM_ERROR", str(e)),
                status_code=500,
            )
        return HTMLResponse(
            content=f'<div class="error">Error: {str(e)}</div>',
            status_code=500,
        )


@router.post("/clear-all-line-items", response_model=None)
async def clear_all_line_items(
    request: Request,
    session_id: str = Form(...),
):
    """Remove all line items."""
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

        session = get_invoice_session(session_id)

        # Clear all line items
        session.invoice_data["line_items"] = []
        session.line_item_count = 0
        session.invoice_data["current_line_item"] = None
        session.has_pending_item = False
        logger.info(f"Cleared all line items for session {session_id}")

        if is_mobile:
            return JSONResponse(
                content=json_success({
                    "success": True,
                    "item_count": 0,
                    "line_items": [],
                })
            )

        return HTMLResponse(
            content='<div class="success">All items cleared.</div>'
        )

    except Exception as e:
        logger.error(f"Error clearing all line items: {str(e)}")
        if is_mobile:
            return JSONResponse(
                content=json_error("CLEAR_ALL_ERROR", str(e)),
                status_code=500,
            )
        return HTMLResponse(
            content=f'<div class="error">Error: {str(e)}</div>',
            status_code=500,
        )
