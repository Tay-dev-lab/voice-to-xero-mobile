"""
Session management for invoice workflow.
"""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from pydantic import BaseModel

from app.api.workflow_base import BaseWorkflowSession

logger = logging.getLogger(__name__)

# Define workflow steps
INVOICE_WORKFLOW_STEPS = [
    "welcome",
    "contact_name",
    "due_date",
    "line_item",
    "line_item_confirm",
    "add_or_review",
    "review",
    "final_submit",
    "complete",
]

# In-memory session storage (for simplicity)
# In production, consider Redis or database storage
_sessions: dict[str, "InvoiceWorkflowSession"] = {}


class InvoiceWorkflowSession(BaseWorkflowSession):
    """Invoice-specific workflow session."""

    def __init__(self, session_id: str | None = None):
        super().__init__(session_id)
        # Invoice-specific data
        self.invoice_data = {
            "contact_name": None,
            "due_date": None,
            "line_items": [],  # Array of line items
            "current_line_item": None,  # Temporary storage during creation
        }
        self.line_item_count = 0
        self.max_line_items = 10
        self.has_pending_item = False  # Track if item needs confirmation
        self.transcripts = {}  # Store transcripts for each step
        self.parsed_results = {}  # Store complete parsed result objects
        self.errors = {}  # Track errors per step

    def get_workflow_steps(self) -> list[str]:
        """Return ordered list of workflow steps."""
        return [
            "welcome",  # Initial state
            "contact_name",  # Step 1: Collect contact name (voice)
            "due_date",  # Step 2: Collect due date (voice)
            "line_item",  # Step 3: Collect line item (voice) - repeatable
            "review",  # Step 4: Review details (buttons only)
            "final_submit",  # Step 5: Final confirmation before Xero
            "complete",  # Final state - invoice created
        ]

    def get_initial_step(self) -> str:
        """Return the first step of the workflow."""
        return "welcome"
    
    def advance_step(self) -> str | None:
        """Override to handle line_item looping."""
        # If we're on line_item with a pending item, stay on line_item
        if self.current_step == "line_item" and self.has_pending_item:
            return self.current_step
        
        # Otherwise use normal advancement
        return super().advance_step()

    def validate_step_data(self, step: str, data: dict[str, Any]) -> bool:
        """Invoice-specific step validation."""
        if step == "contact_name":
            return bool(data.get("contact_name"))
        elif step == "due_date":
            return bool(data.get("due_date"))
        elif step == "line_item":
            # Line item is valid if we have at least one item or a pending item
            return bool(data.get("line_items")) or bool(data.get("current_line_item"))
        # Non-voice steps can always advance
        return step in ["welcome", "review", "final_submit", "complete"]

    # Override parent's can_advance for backward compatibility
    def can_advance(self) -> bool:
        """Check if current step data is complete."""
        return self.validate_step_data(self.current_step, self.invoice_data)

    def parse_invoice_data(self, step: str, parsed_result: Any) -> dict[str, Any]:
        """Parse invoice-specific data from voice input results."""
        data = {}

        if step == "contact_name" and hasattr(parsed_result, "contact_name"):
            data["contact_name"] = parsed_result.contact_name
        elif step == "due_date" and hasattr(parsed_result, "due_date"):
            data["due_date"] = (
                parsed_result.due_date.isoformat() if parsed_result.due_date else None
            )
        elif step == "line_item" and hasattr(parsed_result, "description"):
            # Store as current line item
            data["current_line_item"] = {
                "description": parsed_result.description,
                "quantity": float(parsed_result.quantity),
                "unit_price": float(parsed_result.unit_price),
                "account_code": parsed_result.account_code,
                "vat_rate": parsed_result.vat_rate.value
                if hasattr(parsed_result.vat_rate, "value")
                else parsed_result.vat_rate,
            }

        return data

    def add_line_item(self, item_data: dict):
        """Add a line item to the invoice."""
        if len(self.invoice_data["line_items"]) >= self.max_line_items:
            raise ValueError(f"Maximum {self.max_line_items} line items allowed")

        self.invoice_data["line_items"].append(item_data)
        self.line_item_count = len(self.invoice_data["line_items"])  # Keep in sync
        self.invoice_data["current_line_item"] = None
        self.has_pending_item = False  # Clear pending flag
    
    def clear_current_item(self):
        """Clear the current line item being entered."""
        self.invoice_data["current_line_item"] = None
        self.has_pending_item = False

    def store_step_result(self, step: str, result: BaseModel, transcript: str = ""):
        """Store the result of a step with validation."""
        self.transcripts[step] = transcript
        self.parsed_results[step] = result

        # Parse invoice-specific data
        parsed_data = self.parse_invoice_data(step, result)

        # Update invoice_data and workflow_data
        self.invoice_data.update(parsed_data)
        self.workflow_data.update(parsed_data)
        
        # If this is a line item, set pending flag
        if step == "line_item" and parsed_data.get("current_line_item"):
            self.has_pending_item = True
            logger.info(f"Set has_pending_item=True for line item: {parsed_data['current_line_item']}")

        # Mark step as complete using parent's method (except for line_item)
        if parsed_data and step != "line_item":
            self.mark_step_complete(step, parsed_data)

        logger.info(f"Stored result for step {step}")

    # Step prompts are now defined as a class constant
    STEP_PROMPTS = {
        "welcome": "Welcome! Let's create a new invoice. Click 'Start' to begin.",
        "contact_name": "Please say the contact's full name or organization name.",
        "due_date": "Please say the due date for the invoice (e.g., 'in 30 days' or 'December 31st').",
        "line_item": "Please describe the line item: what it is, quantity, price, and VAT rate (standard, reduced, zero-rated, or exempt).",
        "review": "Review the invoice details below. Click 'Confirm Details' to proceed.",
        "final_submit": "Ready to create this invoice in Xero. Click 'Create Invoice' to submit.",
        "complete": "Invoice created successfully in Xero!",
    }

    def get_step_prompt(self) -> str:
        """Get the prompt for the current step."""
        return self.STEP_PROMPTS.get(self.current_step, "Unknown step")

    def to_invoice_create(self) -> dict | None:
        """Convert session data to invoice creation format."""
        if not all(
            [
                self.invoice_data["contact_name"],
                self.invoice_data["due_date"],
                len(self.invoice_data["line_items"]) > 0,
            ]
        ):
            logger.warning("Cannot create invoice - missing required data")
            return None

        try:
            # Note: This returns a dict ready for Xero API
            # The actual InvoiceCreate model from app/api/models.py will be used later
            return {
                "contact_name": self.invoice_data["contact_name"],
                "due_date": self.invoice_data["due_date"],
                "line_items": self.invoice_data["line_items"],
            }
        except Exception as e:
            logger.error(f"Error creating invoice data: {e}")
            return None

    def get_completed_steps(self) -> list[str]:
        """Get list of steps that have stored data."""
        # Use parent's completed_steps tracking
        return self.completed_steps

    def get_summary(self) -> dict:
        """Get a summary of collected invoice data."""
        base_summary = self.to_dict()  # Use parent's serialization
        base_summary.update(
            {
                "invoice_data": self.invoice_data,
                "has_errors": bool(self.errors),
                "is_complete": self.current_step == "complete",
            }
        )
        return base_summary

    def update_field(self, field_name: str, field_value: str):
        """Update a single field in invoice data."""
        # Handle line item fields (e.g., line_item_0_description)
        if field_name.startswith("line_item_"):
            parts = field_name.split("_")
            if len(parts) >= 4:  # line_item_0_description
                try:
                    idx = int(parts[2])
                    field = "_".join(parts[3:])  # Handle fields like unit_price
                    
                    if idx < len(self.invoice_data.get("line_items", [])):
                        # Convert values to appropriate types
                        if field == "quantity":
                            self.invoice_data["line_items"][idx][field] = float(field_value)
                        elif field == "unit_price":
                            # Remove currency symbol if present
                            clean_value = field_value.replace("£", "").strip()
                            self.invoice_data["line_items"][idx][field] = float(clean_value)
                        else:
                            self.invoice_data["line_items"][idx][field] = field_value
                        
                        logger.info(f"Updated line item {idx} field {field} with value: {field_value}")
                except (ValueError, IndexError) as e:
                    logger.error(f"Error updating line item field {field_name}: {e}")
        # Handle simple invoice fields
        elif field_name in ["contact_name", "contact_id", "due_date"]:
            self.invoice_data[field_name] = field_value
        # Legacy support for contact workflow fields
        elif field_name in ["address_line1", "city", "postal_code", "country"]:
            if self.invoice_data.get("address") is None:
                self.invoice_data["address"] = {}
            # Map to Xero field names
            field_map = {
                "address_line1": "AddressLine1",
                "city": "City",
                "postal_code": "PostalCode",
                "country": "Country",
            }
            self.invoice_data["address"][field_map.get(field_name, field_name)] = field_value
        else:
            # Handle any other simple fields
            self.invoice_data[field_name] = field_value

        self.updated_at = datetime.now(UTC)
        logger.info(f"Updated field {field_name} with value: {field_value}")

    def reset(self):
        """Reset the session to start over."""
        # Reset parent state
        self.current_step = self.get_initial_step()
        self.completed_steps = []
        self.workflow_data = {}
        self.step_errors = {}
        # Reset invoice-specific state
        self.invoice_data = {
            "contact_name": None,
            "due_date": None,
            "line_items": [],
            "current_line_item": None,
        }
        self.line_item_count = 0
        self.transcripts = {}
        self.parsed_results = {}
        self.errors = {}
        self.updated_at = datetime.now(UTC)


# Session management functions
def get_invoice_session(session_id: str | None = None) -> InvoiceWorkflowSession:
    """Get or create an invoice workflow session."""
    if session_id and session_id in _sessions:
        session = _sessions[session_id]
        # Check if session is expired (30 minutes)
        if datetime.now(UTC) - session.updated_at > timedelta(minutes=30):
            logger.info(f"Session {session_id} expired, creating new session")
            del _sessions[session_id]
            session = InvoiceWorkflowSession(session_id)
            _sessions[session_id] = session
    else:
        session = InvoiceWorkflowSession(session_id)
        _sessions[session.session_id] = session
        logger.info(f"Created new session: {session.session_id}")
    return session


def cleanup_expired_sessions():
    """Remove expired sessions from memory."""
    current_time = datetime.now(UTC)
    expired = [
        sid for sid, s in _sessions.items() if current_time - s.updated_at > timedelta(minutes=30)
    ]
    for session_id in expired:
        del _sessions[session_id]
        logger.info(f"Cleaned up expired session: {session_id}")
    return len(expired)
