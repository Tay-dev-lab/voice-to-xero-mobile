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


def render_review_step(session) -> str:
    """
    Render the review step with read-only display of collected data.

    Args:
        session: ContactWorkflowSession object containing workflow data

    Returns:
        Complete HTML for the review step with clean, read-only display
    """
    contact_data = session.contact_data
    address = contact_data.get("address", {})

    # Format address for display
    address_parts = []
    if address.get("AddressLine1"):
        address_parts.append(address.get("AddressLine1"))
    if address.get("City"):
        address_parts.append(address.get("City"))
    if address.get("PostalCode"):
        address_parts.append(address.get("PostalCode"))
    address_display = ", ".join(address_parts) if address_parts else "Not provided"

    return f"""
    <div class="review-section">
        <h2>Review Contact Details</h2>
        <div class="contact-details">
            <div class="detail-row">
                <label>Name:</label>
                <span>{contact_data.get("name", "Not provided")}</span>
            </div>
            <div class="detail-row">
                <label>Email:</label>
                <span>{contact_data.get("email_address", "Not provided")}</span>
            </div>
            <div class="detail-row">
                <label>Address:</label>
                <span>{address_display}</span>
            </div>
        </div>
        <div class="button-container">
            <button class="btn btn-success"
                    hx-post="/contact/proceed-to-submit"
                    hx-vals='{{"session_id": "{session.session_id}"}}'
                    hx-target="#workflow-content"
                    hx-swap="innerHTML">
                Confirm Details
            </button>
        </div>
    </div>
    <script>
        // Update step indicators for review step
        (function() {{
            const steps = document.querySelectorAll('.steps-progress .step');
            const completedSteps = {json.dumps(session.completed_steps if hasattr(session, "completed_steps") else [])};
            
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
        }})();
    </script>
    """


def render_contact_summary(contact_data: dict) -> str:
    """
    Render a summary of contact data for submission.

    Args:
        contact_data: Dictionary containing contact information

    Returns:
        HTML string for contact summary
    """
    is_org = contact_data.get("is_organization", False)
    name_label = "Organization" if is_org else "Contact"

    summary_items = [
        f'<div class="summary-item"><strong>{name_label}:</strong> {contact_data.get("name", "")}</div>'
    ]

    if contact_data.get("email_address"):
        summary_items.append(
            f'<div class="summary-item"><strong>Email:</strong> {contact_data["email_address"]}</div>'
        )

    if contact_data.get("phone"):
        summary_items.append(
            f'<div class="summary-item"><strong>Phone:</strong> {contact_data["phone"]}</div>'
        )

    if contact_data.get("address"):
        address = contact_data["address"]
        address_str = f"{address.get('AddressLine1', '')}, {address.get('City', '')}, {address.get('PostalCode', '')}"
        summary_items.append(
            f'<div class="summary-item"><strong>Address:</strong> {address_str}</div>'
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
        session: ContactWorkflowSession object containing workflow data

    Returns:
        Complete HTML for the submit step
    """
    # Extract contact data from session
    contact_data = session.contact_data

    return f"""
        <div class="workflow-step submit-step" id="step-submit">
            {render_step_header("Ready to Submit", "Your contact will be created in Xero")}
            
            {render_contact_summary(contact_data)}
            
            <div class="submit-actions">
                <button type="button" 
                        class="nav-btn secondary"
                        onclick="goBack()">
                    Back to Review
                </button>
                <button type="button" 
                        class="nav-btn primary submit-btn"
                        onclick="submitToXero()">
                    Create Contact in Xero
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
        session: ContactWorkflowSession object
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
                    hx-post="/contact/confirm-step"
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
          hx-post="/contact/step"
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
            <h3>Contact Created Successfully!</h3>
            <p>{contact_name} has been added to Xero.</p>
            <p class="contact-id">Contact ID: {contact_id}</p>
            <div class="success-actions">
                <button type="button" 
                        class="nav-btn secondary"
                        onclick="window.location.href='/contact/new'">
                    Add Another Contact
                </button>
                <button type="button" 
                        class="nav-btn primary"
                        onclick="window.location.href='/'">
                    Return to Dashboard
                </button>
            </div>
        </div>
    """
