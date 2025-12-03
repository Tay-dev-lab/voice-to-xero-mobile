"""
Template rendering functions for contact workflow UI components.

This module contains functions that generate HTML for different workflow steps.
Functions are broken down into small, focused components following CLAUDE.md standards.
"""

import json


def render_step_header(step_title: str, step_description: str = "") -> str:
    """
    Render the header section for a workflow step.

    Args:
        step_title: The title of the current step
        step_description: Optional description text for the step

    Returns:
        HTML string for the step header
    """
    return f"""
        <div class="step-header">
            <h2 class="step-title">{step_title}</h2>
            {f'<p class="step-description">{step_description}</p>' if step_description else ""}
        </div>
    """


def render_voice_input_section(step_name: str, field_name: str = "") -> str:
    """
    Render voice input controls for a workflow step.

    Args:
        step_name: Name of the current step
        field_name: Optional field name for the input

    Returns:
        HTML string for voice input section
    """
    return f"""
        <div class="voice-section">
            <button type="button" 
                    id="record-btn" 
                    class="record-btn"
                    onclick="toggleRecording('{step_name}')">
                <svg class="mic-icon" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3z"/>
                    <path d="M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z"/>
                </svg>
                <span class="btn-text">Start Recording</span>
            </button>
            <div id="recording-indicator" class="recording-indicator" style="display: none;">
                <span class="pulse"></span>
                Recording...
            </div>
            <div id="transcription-result" class="transcription-result" style="display: none;">
                <div class="transcription-text"></div>
            </div>
        </div>
    """


def render_text_input_section(
    field_name: str, field_type: str = "text", placeholder: str = "", value: str = ""
) -> str:
    """
    Render text input field for manual entry.

    Args:
        field_name: Name attribute for the input field
        field_type: HTML input type (text, email, tel, etc.)
        placeholder: Placeholder text for the input
        value: Initial value for the input

    Returns:
        HTML string for text input section
    """
    return f'''
        <div class="text-input-section">
            <label for="{field_name}_text" class="input-label">Or type manually:</label>
            <input type="{field_type}" 
                   id="{field_name}_text" 
                   name="{field_name}_text"
                   class="text-input"
                   placeholder="{placeholder}"
                   value="{value}">
        </div>
    '''


def render_error_section() -> str:
    """
    Render error display section.

    Returns:
        HTML string for error display area
    """
    return """
        <div id="error-message" class="error-message" style="display: none;"></div>
    """


def render_step_navigation(step_name: str, show_back: bool = False, show_skip: bool = False) -> str:
    """
    Render navigation buttons for a workflow step.

    Args:
        step_name: Name of the current step
        show_back: Whether to show the back button
        show_skip: Whether to show the skip button

    Returns:
        HTML string for navigation buttons
    """
    buttons = []

    if show_back:
        buttons.append("""
            <button type="button" 
                    class="nav-btn secondary"
                    onclick="goBack()">
                Back
            </button>
        """)

    if show_skip:
        buttons.append(f"""
            <button type="button" 
                    class="nav-btn secondary"
                    onclick="skipStep('{step_name}')">
                Skip
            </button>
        """)

    buttons.append(f"""
        <button type="button" 
                class="nav-btn primary"
                id="confirm-btn"
                onclick="confirmStep('{step_name}')"
                disabled>
            Confirm
        </button>
    """)

    return f"""
        <div class="navigation-buttons">
            {" ".join(buttons)}
        </div>
    """


def render_data_collection_step(
    step_name: str,
    step_title: str,
    step_description: str = "",
    field_type: str = "text",
    placeholder: str = "",
    show_skip: bool = False,
    show_back: bool = False,
) -> str:
    """
    Compose a complete data collection step from components.

    This orchestrates the rendering of various UI components for a workflow step.
    Keeps function under 50 lines per CLAUDE.md standards.

    Args:
        step_name: Internal name of the step
        step_title: Display title for the step
        step_description: Optional description text
        field_type: HTML input type for text field
        placeholder: Placeholder text for input
        show_skip: Whether to show skip button
        show_back: Whether to show back button

    Returns:
        Complete HTML for the data collection step
    """
    return f'''
        <div class="workflow-step" id="step-{step_name}">
            {render_step_header(step_title, step_description)}
            
            <div class="input-container">
                {render_voice_input_section(step_name)}
                {render_text_input_section(step_name, field_type, placeholder)}
            </div>
            
            {render_error_section()}
            {render_step_navigation(step_name, show_back, show_skip)}
            
            <input type="hidden" id="{step_name}_value" name="{step_name}">
        </div>
    '''


def render_editable_field(
    field_name: str, field_label: str, field_value: str, field_type: str = "text"
) -> str:
    """
    Render an editable field in the review step.

    Args:
        field_name: Internal field name
        field_label: Display label for the field
        field_value: Current value of the field
        field_type: HTML input type

    Returns:
        HTML string for editable field
    """
    return f'''
        <div class="field-group">
            <label class="field-label">{field_label}:</label>
            <div class="field-value-container">
                <span class="field-value" id="{field_name}_display">{field_value or "Not provided"}</span>
                <button type="button" 
                        class="edit-btn"
                        onclick="editField('{field_name}')">
                    Edit
                </button>
            </div>
            <div class="field-edit" id="{field_name}_edit" style="display: none;">
                <input type="{field_type}" 
                       class="edit-input"
                       id="{field_name}_input"
                       value="{field_value}">
                <div class="edit-actions">
                    <button type="button" 
                            class="save-btn"
                            onclick="saveField('{field_name}')">
                        Save
                    </button>
                    <button type="button" 
                            class="cancel-btn"
                            onclick="cancelEdit('{field_name}')">
                        Cancel
                    </button>
                </div>
            </div>
        </div>
    '''


def render_line_item_confirm(session, session_id: str) -> str:
    """
    Render the line item confirmation step with Add Another / Review options.
    
    Args:
        session: InvoiceWorkflowSession object containing workflow data
        session_id: Current session ID
    
    Returns:
        HTML for line item confirmation with action buttons
    """
    # Get the current item being confirmed and existing items
    current_item = session.invoice_data.get("current_line_item", {})
    existing_items = session.invoice_data.get("line_items", [])
    item_count = len(existing_items) + 1  # +1 for current item
    
    # Calculate item total and VAT
    quantity = float(current_item.get("quantity", 0))
    unit_price = float(current_item.get("unit_price", 0))
    item_total = quantity * unit_price
    
    # Calculate VAT based on rate
    vat_rate = current_item.get("vat_rate", "standard")
    vat_amount = 0
    if vat_rate == "standard":
        vat_amount = item_total * 0.20
    elif vat_rate == "reduced":
        vat_amount = item_total * 0.05
    # zero_rated and exempt have 0 VAT
    
    item_total_with_vat = item_total + vat_amount
    
    # Calculate running total (existing items + current item)
    running_subtotal = sum(
        float(item["quantity"]) * float(item["unit_price"]) 
        for item in existing_items
    ) + item_total
    
    # Format VAT rate for display
    vat_display = vat_rate.replace("_", " ").title()
    
    return f"""
    <div class="line-item-confirm-section">
        <h2>Item {item_count} Details</h2>
        
        <div class="item-details-card">
            <div class="item-detail-row">
                <label>Description:</label>
                <span class="item-value">{current_item.get("description", "")}</span>
            </div>
            <div class="item-detail-row">
                <label>Quantity:</label>
                <span class="item-value">{quantity}</span>
            </div>
            <div class="item-detail-row">
                <label>Unit Price:</label>
                <span class="item-value">£{unit_price:.2f}</span>
            </div>
            <div class="item-detail-row">
                <label>VAT Rate:</label>
                <span class="item-value">{vat_display}</span>
            </div>
            <div class="item-detail-row item-total">
                <label>Item Total:</label>
                <span class="item-value">£{item_total:.2f}</span>
            </div>
            {f'''<div class="item-detail-row">
                <label>VAT Amount:</label>
                <span class="item-value">£{vat_amount:.2f}</span>
            </div>''' if vat_amount > 0 else ''}
            <div class="item-detail-row grand-total">
                <label>Total with VAT:</label>
                <span class="item-value">£{item_total_with_vat:.2f}</span>
            </div>
        </div>
        
        {f'''
        <div class="running-total-info">
            <p class="items-added">{len(existing_items)} item{"s" if len(existing_items) != 1 else ""} already added</p>
            <p class="running-total">Running Subtotal: £{running_subtotal:.2f}</p>
        </div>
        ''' if existing_items else ''}
        
        <div class="action-buttons">
            <button class="btn btn-primary btn-large"
                    hx-post="/invoice/add-another-item"
                    hx-vals='{{"session_id": "{session_id}"}}'
                    hx-target="#workflow-content"
                    hx-swap="innerHTML">
                <svg class="btn-icon" width="20" height="20" viewBox="0 0 20 20" fill="currentColor">
                    <path d="M10 5a1 1 0 011 1v3h3a1 1 0 110 2h-3v3a1 1 0 11-2 0v-3H6a1 1 0 110-2h3V6a1 1 0 011-1z"/>
                </svg>
                Add Another Item
            </button>
            
            <button class="btn btn-success btn-large"
                    hx-post="/invoice/proceed-to-review"
                    hx-vals='{{"session_id": "{session_id}"}}'
                    hx-target="#workflow-content"
                    hx-swap="innerHTML">
                <svg class="btn-icon" width="20" height="20" viewBox="0 0 20 20" fill="currentColor">
                    <path d="M9 2a1 1 0 000 2h2a1 1 0 100-2H9z"/>
                    <path fill-rule="evenodd" d="M4 5a2 2 0 012-2 1 1 0 000 2H6a2 2 0 00-2 2v6a2 2 0 002 2h8a2 2 0 002-2V7a2 2 0 00-2-2h-1a1 1 0 100-2h1a4 4 0 014 4v6a4 4 0 01-4 4H6a4 4 0 01-4-4V7a4 4 0 014-4z" clip-rule="evenodd"/>
                </svg>
                Review Invoice
            </button>
        </div>
        
        <div class="item-limit-info">
            <small>You can add up to {session.max_line_items} items. Currently: {item_count} of {session.max_line_items}</small>
        </div>
    </div>
    
    <script>
        // Update step indicators
        (function() {{
            const steps = document.querySelectorAll('.steps-progress .step');
            const completedSteps = {json.dumps(session.completed_steps if hasattr(session, "completed_steps") else [])};
            
            steps.forEach(s => {{
                s.classList.remove('active', 'completed');
                
                const stepName = s.dataset.step;
                const isCompleted = completedSteps.includes(stepName);
                const isCurrent = stepName === 'line_item';
                
                if (isCurrent) {{
                    s.classList.add('active');
                }} else if (isCompleted) {{
                    s.classList.add('completed');
                }}
            }});
            
            // Update global state
            window.currentStep = 'line_item_confirm';
        }})();
    </script>
    """


def render_review_step(session, session_id: str) -> str:
    """
    Render the review step with read-only display of collected invoice data.

    Args:
        session: InvoiceWorkflowSession object containing workflow data
        session_id: Current session ID

    Returns:
        Complete HTML for the review step with clean, read-only display
    """
    invoice_data = session.invoice_data

    # Calculate totals
    subtotal = 0
    vat_total = 0

    # Line items HTML
    line_items_html = ""
    for idx, item in enumerate(invoice_data.get("line_items", []), 1):
        item_total = float(item["quantity"]) * float(item["unit_price"])
        subtotal += item_total

        # Calculate VAT based on rate
        vat_rate_display = item["vat_rate"].replace("_", " ").title()
        vat_amount = 0
        if item["vat_rate"] == "standard":
            vat_amount = item_total * 0.20
        elif item["vat_rate"] == "reduced":
            vat_amount = item_total * 0.05
        # zero_rated and exempt have 0 VAT

        vat_total += vat_amount

        line_items_html += f"""
        <tr>
            <td>{idx}</td>
            <td>{item["description"]}</td>
            <td>{int(item["quantity"])}</td>
            <td>£{item["unit_price"]:.2f}</td>
            <td>{vat_rate_display}</td>
            <td>£{item_total:.2f}</td>
        </tr>
        """

    grand_total = subtotal + vat_total

    return f"""
    <div class="review-section">
        <h2>Review Invoice Details</h2>
        
        <div class="invoice-header-details">
            <div class="detail-row">
                <label>Contact Name:</label>
                <span>{invoice_data.get("contact_name", "Not provided")}</span>
            </div>
            <div class="detail-row">
                <label>Due Date:</label>
                <span>{invoice_data.get("due_date", "Not provided")}</span>
            </div>
        </div>
        
        <div class="line-items-table">
            <h3>Invoice Items</h3>
            <table class="items-table">
                <thead>
                    <tr>
                        <th>#</th>
                        <th>Description</th>
                        <th>Qty</th>
                        <th>Unit Price</th>
                        <th>VAT Rate</th>
                        <th>Total</th>
                    </tr>
                </thead>
                <tbody>
                    {line_items_html}
                </tbody>
            </table>
        </div>
        
        <div class="invoice-totals">
            <div class="total-row">
                <label>Subtotal:</label>
                <span>£{subtotal:.2f}</span>
            </div>
            <div class="total-row">
                <label>VAT:</label>
                <span>£{vat_total:.2f}</span>
            </div>
            <div class="total-row grand-total">
                <label>Total:</label>
                <span>£{grand_total:.2f}</span>
            </div>
        </div>
        
        <div class="button-container">
            <button class="btn btn-secondary"
                    hx-post="/invoice/add-another-item"
                    hx-vals='{{"session_id": "{session_id}"}}'
                    hx-target="#workflow-content"
                    hx-swap="innerHTML">
                Add More Items
            </button>
            <button class="btn btn-success"
                    hx-post="/invoice/proceed-to-submit"
                    hx-vals='{{"session_id": "{session_id}"}}'
                    hx-target="#workflow-content"
                    hx-swap="innerHTML">
                Confirm Invoice
            </button>
        </div>
    </div>
    <script>
        // Update step indicators for review step
        (function() {{
            const steps = document.querySelectorAll('.steps-progress .step');
            // All data collection steps should be marked as completed when on review
            const completedSteps = ['contact_name', 'due_date', 'line_item'];
            
            steps.forEach(s => {{
                s.classList.remove('active', 'completed');
                
                const stepName = s.dataset.step;
                const isCompleted = completedSteps.includes(stepName);
                const isCurrent = stepName === 'review';
                
                if (isCurrent) {{
                    // Current step (review) gets only active class (blue)
                    s.classList.add('active');
                }} else if (isCompleted) {{
                    // Completed steps get completed class (green)
                    s.classList.add('completed');
                }}
            }});
            
            // Update step clickability
            if (window.updateStepClickability) {{
                window.updateStepClickability();
            }}
            
            // Update global state
            window.currentStep = 'review';
            window.completedSteps = ['contact_name', 'due_date', 'line_item'];
        }})();
    </script>
    """


def render_invoice_summary(invoice_data: dict) -> str:
    """
    Render a summary of invoice data for submission.

    Args:
        invoice_data: Dictionary containing invoice information

    Returns:
        HTML string for invoice summary
    """
    summary_items = []
    
    # Add contact name
    if invoice_data.get("contact_name"):
        summary_items.append(
            f'<div class="summary-item"><strong>Contact:</strong> {invoice_data["contact_name"]}</div>'
        )
    
    # Add due date
    if invoice_data.get("due_date"):
        summary_items.append(
            f'<div class="summary-item"><strong>Due Date:</strong> {invoice_data["due_date"]}</div>'
        )
    
    # Add line items count
    line_items = invoice_data.get("line_items", [])
    if line_items:
        summary_items.append(
            f'<div class="summary-item"><strong>Line Items:</strong> {len(line_items)} items</div>'
        )

    return f"""
        <div class="contact-summary">
            {"".join(summary_items)}
        </div>
    """


def render_submit_step(session) -> str:
    """
    Render the final submission step.

    Orchestrates rendering of the submission UI.
    Keeps function under 50 lines per CLAUDE.md standards.

    Args:
        session: InvoiceWorkflowSession object containing workflow data

    Returns:
        Complete HTML for the submit step
    """
    # Extract invoice data from session
    invoice_data = session.invoice_data

    return f"""
        <div class="workflow-step submit-step" id="step-submit">
            {render_step_header("Ready to Submit", "Your invoice will be created in Xero")}
            
            {render_invoice_summary(invoice_data)}
            
            <div class="submit-actions">
                <button type="button" 
                        class="nav-btn secondary"
                        onclick="goBack()">
                    Back to Review
                </button>
                <button type="button" 
                        class="nav-btn primary submit-btn"
                        onclick="submitToXero()">
                    Create Invoice in Xero
                </button>
            </div>
            
            <div id="submit-status" class="submit-status" style="display: none;"></div>
            {render_error_section()}
        </div>
    """


def render_step_with_state(session, step: str) -> str:
    """
    Render a data collection step with its preserved state from session.

    Args:
        session: InvoiceWorkflowSession object
        step: Name of the step to render (name, email, address)

    Returns:
        HTML string for the step with existing data displayed
    """
    # Get step-specific data
    transcript = session.transcripts.get(step, "")
    parsed_result = session.parsed_results.get(step)
    session_id = session.session_id

    # Get step prompt
    prompt = session.STEP_PROMPTS.get(step, "")

    # Build the result display if data exists
    result_html = ""
    if transcript and parsed_result:
        if step == "name":
            value = getattr(parsed_result, "name", "")
            result_html = f'''
            <div class="transcription-result">
                <p class="transcript-label">You said: "{transcript}"</p>
                <p class="parsed-result">Understood: <strong>{value}</strong></p>
            </div>'''
        elif step == "email":
            value = getattr(parsed_result, "email_address", "")
            result_html = f'''
            <div class="transcription-result">
                <p class="transcript-label">You said: "{transcript}"</p>
                <p class="parsed-result">Email: <strong>{value}</strong></p>
            </div>'''
        elif step == "address":
            result_html = f'''
            <div class="transcription-result">
                <p class="transcript-label">You said: "{transcript}"</p>
                <p class="parsed-result">Address: <strong>{getattr(parsed_result, "address_line1", "")}, {getattr(parsed_result, "city", "")}, {getattr(parsed_result, "postal_code", "")}</strong></p>
            </div>'''

    # Determine if continue button should be enabled
    has_data = step in session.completed_steps

    return f'''
    <div id="step-prompt" class="prompt-section">
        <h3>{prompt}</h3>
    </div>
    <div id="voice-recorder" class="recorder-section">
        <div class="button-container">
            <button id="confirm-step-btn" class="btn btn-primary btn-large" 
                    {"" if has_data else "disabled"}
                    hx-post="/invoice/confirm-step"
                    hx-vals='{{"session_id": "{session_id}", "step": "{step}"}}'
                    hx-target="#workflow-content"
                    hx-swap="innerHTML">
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
        <input type="hidden" name="step" id="current-step" value="{step}">
        <input type="file" name="audio-file" id="audio-file" accept="audio/*">
    </form>
    <div id="step-result" class="result-section">
        {result_html}
    </div>
    <script>
        // Update global state
        window.currentStep = '{step}';
        window.sessionId = '{session_id}';
        window.hasRecorded = {"true" if has_data else "false"};
        
        // Reinitialize voice recorder
        if (window.initVoiceRecorder) {{
            window.initVoiceRecorder();
        }}
        
        // Update step indicators
        (function() {{
            const steps = document.querySelectorAll('.steps-progress .step');
            const completedSteps = {json.dumps(session.completed_steps if hasattr(session, "completed_steps") else [])};
            
            steps.forEach(s => {{
                s.classList.remove('active', 'completed');
                
                const stepName = s.dataset.step;
                const isCompleted = completedSteps.includes(stepName);
                const isCurrent = stepName === '{step}';
                
                if (isCurrent) {{
                    // Current step gets only active class (blue)
                    s.classList.add('active');
                }} else if (isCompleted) {{
                    // Completed steps get completed class (green)
                    s.classList.add('completed');
                }}
            }});
            
            if (window.updateStepClickability) {{
                window.updateStepClickability();
            }}
        }})();
    </script>
    '''


def render_invoice_step_with_state(session, step: str) -> str:
    """
    Render an invoice workflow step with its preserved state from session.
    
    Args:
        session: InvoiceWorkflowSession object
        step: Name of the step to render (contact_name, due_date, line_item)
    
    Returns:
        HTML string for the step with existing data and continue button
    """
    invoice_data = session.invoice_data
    session_id = session.session_id
    
    # Determine completed steps
    completed_steps = []
    if invoice_data.get("contact_name"):
        completed_steps.append("contact_name")
    if invoice_data.get("due_date"):
        completed_steps.append("due_date")
    if invoice_data.get("line_items"):
        completed_steps.append("line_item")
    
    if step == "contact_name":
        existing_value = invoice_data.get("contact_name", "")
        has_value = bool(existing_value)
        return f"""
        <div id="step-prompt" class="prompt-section">
            <h3>Who is this invoice for?</h3>
        </div>
        <div id="voice-recorder" class="recorder-section">
            <div class="button-container">
                <button id="confirm-step-btn" class="btn btn-primary btn-large" 
                        {"" if has_value else "disabled"}
                        hx-post="/invoice/confirm-step"
                        hx-vals='{{"session_id": "{session_id}", "step": "contact_name"}}'
                        hx-target="#workflow-content"
                        hx-swap="innerHTML">
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
            <input type="hidden" name="step" id="current-step" value="contact_name">
            <input type="file" name="audio-file" id="audio-file" accept="audio/*">
        </form>
        <div id="step-result" class="result-section">
            {f'<div class="existing-value">Current value: <strong>{existing_value}</strong></div>' if existing_value else ''}
        </div>
        <script>
            // Update global state
            window.currentStep = 'contact_name';
            window.sessionId = '{session_id}';
            window.hasRecorded = {"true" if has_value else "false"};
            
            // Update step indicators
            updateStepIndicators('contact_name', {json.dumps(completed_steps)});
            
            // Reinitialize voice recorder
            if (window.initVoiceRecorder) {{
                window.initVoiceRecorder();
            }}
        </script>
        """
    
    elif step == "due_date":
        existing_value = invoice_data.get("due_date", "")
        has_value = bool(existing_value)
        return f"""
        <div id="step-prompt" class="prompt-section">
            <h3>When should this invoice be paid?</h3>
        </div>
        <div id="voice-recorder" class="recorder-section">
            <div class="button-container">
                <button id="confirm-step-btn" class="btn btn-primary btn-large" 
                        {"" if has_value else "disabled"}
                        hx-post="/invoice/confirm-step"
                        hx-vals='{{"session_id": "{session_id}", "step": "due_date"}}'
                        hx-target="#workflow-content"
                        hx-swap="innerHTML">
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
            <input type="hidden" name="step" id="current-step" value="due_date">
            <input type="file" name="audio-file" id="audio-file" accept="audio/*">
        </form>
        <div id="step-result" class="result-section">
            {f'<div class="existing-value">Current value: <strong>{existing_value}</strong></div>' if existing_value else ''}
        </div>
        <script>
            // Update global state
            window.currentStep = 'due_date';
            window.sessionId = '{session_id}';
            window.hasRecorded = {"true" if has_value else "false"};
            
            // Update step indicators
            updateStepIndicators('due_date', {json.dumps(completed_steps)});
            
            // Reinitialize voice recorder
            if (window.initVoiceRecorder) {{
                window.initVoiceRecorder();
            }}
        </script>
        """
    
    elif step == "line_item":
        # For line items, show the confirmation interface with existing items
        line_items_html = ""
        subtotal = 0
        vat_total = 0
        
        for _idx, item in enumerate(invoice_data.get("line_items", []), 1):
            item_total = float(item["quantity"]) * float(item["unit_price"])
            subtotal += item_total
            
            # Calculate VAT
            if item["vat_rate"] == "standard":
                vat_total += item_total * 0.20
            elif item["vat_rate"] == "reduced":
                vat_total += item_total * 0.05
            
            line_items_html += f"""
            <tr>
                <td>{item["description"]}</td>
                <td>{int(item["quantity"])}</td>
                <td>£{item["unit_price"]:.2f}</td>
            </tr>
            """
        
        grand_total = subtotal + vat_total
        
        return f"""
        <div class="workflow-step" id="step-line-item">
            {render_step_header("Line Items", "Add items to your invoice")}
            
            <div class="summary-section">
                <h3>Current Invoice Items</h3>
                <table class="summary-table">
                    <thead>
                        <tr>
                            <th>Description</th>
                            <th>Qty</th>
                            <th>Price</th>
                        </tr>
                    </thead>
                    <tbody>
                        {line_items_html if line_items_html else '<tr><td colspan="3">No items added yet</td></tr>'}
                    </tbody>
                </table>
                
                <div class="totals-section">
                    <div class="total-row">
                        <span>Subtotal:</span>
                        <span>£{subtotal:.2f}</span>
                    </div>
                    <div class="total-row">
                        <span>VAT:</span>
                        <span>£{vat_total:.2f}</span>
                    </div>
                    <div class="total-row grand-total">
                        <span>Total:</span>
                        <span>£{grand_total:.2f}</span>
                    </div>
                </div>
            </div>
            
            {render_voice_input_section("line_item")}
            
            <div class="button-container">
                <button class="btn btn-secondary"
                        hx-post="/invoice/add-another-item"
                        hx-vals='{{"session_id": "{session_id}"}}'
                        hx-target="#workflow-content"
                        hx-swap="innerHTML">
                    Add Another Item
                </button>
                <button class="btn btn-primary"
                        {"disabled" if not line_items_html else ""}
                        hx-post="/invoice/proceed-to-review"
                        hx-vals='{{"session_id": "{session_id}"}}'
                        hx-target="#workflow-content"
                        hx-swap="innerHTML">
                    Continue to Review
                </button>
            </div>
            {render_error_section()}
        </div>
        <script>
            window.currentStep = 'line_item';
            window.sessionId = '{session_id}';
            updateStepIndicators('line_item', {json.dumps(completed_steps)});
        </script>
        """
    
    return render_error_section()


def render_success_message(contact_name: str, contact_id: str) -> str:
    """
    Render success message after contact creation.

    Args:
        contact_name: Name of the created contact
        contact_id: Xero contact ID

    Returns:
        HTML string for success message
    """
    return f"""
        <div class="success-message">
            <svg class="success-icon" viewBox="0 0 24 24" fill="currentColor">
                <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41L9 16.17z"/>
            </svg>
            <h3>Invoice Created Successfully!</h3>
            <p>{contact_name} has been added to Xero.</p>
            <p class="contact-id">Invoice ID: {contact_id}</p>
            <div class="success-actions">
                <button type="button" 
                        class="nav-btn secondary"
                        onclick="window.location.href='/invoice/new'">
                    Add Another Invoice
                </button>
                <button type="button" 
                        class="nav-btn primary"
                        onclick="window.location.href='/'">
                    Return to Dashboard
                </button>
            </div>
        </div>
    """
