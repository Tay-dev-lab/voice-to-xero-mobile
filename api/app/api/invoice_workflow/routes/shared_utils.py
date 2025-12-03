"""
Shared utilities and helper functions for contact workflow routes.

This module contains general utility functions used across the workflow.
Template rendering functions have been moved to template_renderers.py.
Authentication functions have been moved to auth_utils.py.
"""

import logging
from pathlib import Path

from fastapi.templating import Jinja2Templates
from slowapi import Limiter

from app.api.common.utils import get_session_or_ip

logger = logging.getLogger(__name__)

# Initialize templates
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent.parent.parent / "templates"))

# Initialize limiter with custom key function
limiter = Limiter(key_func=get_session_or_ip)


def get_step_title(step: str) -> str:
    """Get display title for step."""
    titles = {
        "welcome": "Welcome",
        # Invoice workflow steps
        "contact_name": "Contact Name",
        "due_date": "Due Date",
        "line_item": "Line Item",
        "line_item_confirm": "Confirm Line Item",
        "add_or_review": "Add or Review",
        # Legacy contact workflow steps
        "name": "Contact Name",
        "email": "Email Address",
        "address": "Contact Address",
        # Common steps
        "review": "Review Details",
        "final_submit": "Final Confirmation",
        "complete": "Complete",
    }
    return titles.get(step, step.title())


def get_step_prompts() -> dict[str, str]:
    """Get voice prompts for each step."""
    return {
        "welcome": "Welcome! Let's create a new invoice. Click 'Start' to begin.",
        # Invoice workflow steps
        "contact_name": "Please say the contact's full name or organization name.",
        "due_date": "Please say the due date for the invoice (e.g., 'in 30 days' or 'December 31st').",
        "line_item": "Please describe the line item: what it is, quantity, price, and VAT rate.",
        "line_item_confirm": "Please confirm the line item details below.",
        "add_or_review": "Would you like to add another item or review the invoice?",
        # Legacy contact workflow steps
        "name": "Please say the contact's full name or organization name.",
        "email": "Please say the contact's email address.",
        "address": "Please say the full address including street, city, and postal code.",
        # Common steps
        "review": "Review the invoice details below.",
        "final_submit": "Ready to create this invoice in Xero.",
        "complete": "Invoice created successfully!",
    }


def format_parsed_result(step: str, result) -> str:
    """Format parsed result for display."""
    # Invoice workflow steps
    if step == "contact_name":
        return f"Contact: {getattr(result, 'contact_name', 'N/A')}"
    elif step == "due_date":
        return f"Due Date: {getattr(result, 'due_date', 'N/A')}"
    elif step == "line_item":
        lines = []
        if hasattr(result, "description"):
            lines.append(f"Description: {result.description}")
        if hasattr(result, "quantity"):
            lines.append(f"Quantity: {result.quantity}")
        if hasattr(result, "unit_price"):
            lines.append(f"Unit Price: £{result.unit_price}")
        if hasattr(result, "vat_rate"):
            vat = result.vat_rate
            if hasattr(vat, "value"):
                vat = vat.value
            lines.append(f"VAT Rate: {vat.replace('_', ' ').title()}")
        return "<br>".join(lines)
    # Legacy contact workflow steps
    elif step == "name":
        return f"Name: {getattr(result, 'name', 'N/A')}"
    elif step == "email":
        return f"Email: {getattr(result, 'email_address', 'N/A')}"
    elif step == "address":
        lines = []
        if hasattr(result, "address_line1"):
            lines.append(f"Address: {result.address_line1}")
        if hasattr(result, "city"):
            lines.append(f"City: {result.city}")
        if hasattr(result, "postal_code"):
            lines.append(f"Postal Code: {result.postal_code}")
        if hasattr(result, "country"):
            lines.append(f"Country: {result.country}")
        return "<br>".join(lines)
    return str(result)


def generate_step_result_html(step: str, parsed_result, transcript: str, session_id: str) -> str:
    """
    Generate the HTML for a completed step result.

    Args:
        step: The current workflow step
        parsed_result: The parsed result object from the step
        transcript: The original voice transcript
        session_id: The current session ID

    Returns:
        HTML string for the step result display
    """
    # Format the parsed data for display
    formatted_data = ""

    # Handle invoice workflow steps
    if step == "contact_name" and hasattr(parsed_result, "contact_name"):
        is_org = getattr(parsed_result, "is_organization", False)
        org_text = " (Organization)" if is_org else " (Individual)"
        formatted_data = f"{parsed_result.contact_name}{org_text}"
    elif step == "due_date" and hasattr(parsed_result, "due_date"):
        due_date = parsed_result.due_date
        days_from_now = getattr(parsed_result, "days_from_now", None)
        if days_from_now:
            formatted_data = f"{due_date} ({days_from_now} days from today)"
        else:
            formatted_data = str(due_date)
    elif step == "line_item" and hasattr(parsed_result, "description"):
        # Format line item details
        desc = parsed_result.description
        qty = parsed_result.quantity
        price = parsed_result.unit_price
        vat = getattr(parsed_result, "vat_rate", "standard")
        # Handle VAT rate enum value
        if hasattr(vat, "value"):
            vat = vat.value
        vat_display = vat.replace("_", " ").title()
        formatted_data = f"""
        <strong>{desc}</strong><br>
        Quantity: {qty}<br>
        Unit Price: £{price}<br>
        VAT Rate: {vat_display}
        """
    # Legacy contact workflow support (if still needed)
    elif step == "name" and hasattr(parsed_result, "name"):
        is_org = getattr(parsed_result, "is_organization", False)
        org_text = " (Organization)" if is_org else " (Individual)"
        formatted_data = f"{parsed_result.name}{org_text}"
    elif step == "email" and hasattr(parsed_result, "email_address"):
        formatted_data = parsed_result.email_address
    elif step == "address" and hasattr(parsed_result, "address_line1"):
        address_parts = []
        address_parts.append(parsed_result.address_line1)
        if hasattr(parsed_result, "address_line2") and parsed_result.address_line2:
            address_parts.append(parsed_result.address_line2)
        city_line = (
            f"{getattr(parsed_result, 'city', '')}, {getattr(parsed_result, 'postal_code', '')}"
        )
        address_parts.append(city_line)
        address_parts.append(getattr(parsed_result, "country", "GB"))
        formatted_data = "<br>".join(address_parts)

    # Generate the complete HTML response with success indicator (no duplicate button)
    html_content = f'''
    <div class="success-indicator">
        <span class="checkmark">✓</span>
        <span>I heard:</span>
    </div>
    <div class="parsed-data">
        <div class="data-box">
            {formatted_data}
        </div>
    </div>
    <div class="transcript">
        <em>"{transcript}"</em>
    </div>
    <script>
        // Enable the existing Continue button in the recorder section
        (function() {{
            const confirmBtn = document.getElementById('confirm-step-btn');
            if (confirmBtn) {{
                confirmBtn.disabled = false;
                confirmBtn.classList.remove('disabled');
                
                // Update HTMX attributes for the button
                confirmBtn.setAttribute('hx-post', '/invoice/confirm-step');
                confirmBtn.setAttribute('hx-vals', JSON.stringify({{
                    session_id: '{session_id}',
                    step: '{step}'
                }}));
                confirmBtn.setAttribute('hx-target', '#workflow-content');
                confirmBtn.setAttribute('hx-swap', 'innerHTML');
                
                // Re-process with HTMX to activate the button
                if (typeof htmx !== 'undefined') {{
                    htmx.process(confirmBtn);
                }}
            }}
            
            // Update record button text
            const recordBtn = document.getElementById('record-button');
            if (recordBtn) {{
                const btnText = recordBtn.querySelector('.btn-text');
                if (btnText) {{
                    btnText.textContent = 'Hold to Re-record';
                }}
            }}
            
            // Mark that recording has been done for this step
            window.hasRecorded = true;
            
            // Trigger custom event for step completion
            document.body.dispatchEvent(new CustomEvent('step-recorded', {{
                detail: {{ step: '{step}', session_id: '{session_id}' }}
            }}));
        }})();
    </script>
    '''

    return html_content


def format_address_display(address_data) -> str:
    """
    Format address data for display.

    Args:
        address_data: Dictionary containing address fields

    Returns:
        Formatted address string
    """
    if not address_data:
        return "Not provided"

    parts = [
        address_data.get("AddressLine1", ""),
        address_data.get("City", ""),
        address_data.get("PostalCode", ""),
        address_data.get("Country", ""),
    ]
    return ", ".join(p for p in parts if p)
