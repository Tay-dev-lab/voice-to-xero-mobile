"""
Session management for contact workflow.
"""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from pydantic import BaseModel

from app.api.models import ContactCreate, StreetAddress
from app.api.workflow_base import BaseWorkflowSession

logger = logging.getLogger(__name__)

# Define workflow steps
CONTACT_WORKFLOW_STEPS = [
    "welcome",
    "name",
    "email",
    "address",
    "review",
    "final_submit",
    "complete",
]

# In-memory session storage (for simplicity)
# In production, consider Redis or database storage
_sessions: dict[str, "ContactWorkflowSession"] = {}


class ContactWorkflowSession(BaseWorkflowSession):
    """Contact-specific workflow session."""

    def __init__(self, session_id: str | None = None):
        super().__init__(session_id)
        # Contact-specific data
        self.contact_data = {
            "name": None,
            "email_address": None,
            "address": None,
        }
        self.transcripts = {}  # Store transcripts for each step
        self.parsed_results = {}  # Store complete parsed result objects
        self.errors = {}  # Track errors per step

    def get_workflow_steps(self) -> list[str]:
        """Return ordered list of workflow steps."""
        return [
            "welcome",  # Initial state
            "name",  # Step 1: Collect name (voice)
            "email",  # Step 2: Collect email (voice)
            "address",  # Step 3: Collect address (voice)
            "review",  # Step 4: Review details (buttons only)
            "final_submit",  # Step 5: Final confirmation before Xero
            "complete",  # Final state - contact created
        ]

    def get_initial_step(self) -> str:
        """Return the first step of the workflow."""
        return "welcome"

    def validate_step_data(self, step: str, data: dict[str, Any]) -> bool:
        """Contact-specific step validation."""
        if step == "name":
            return bool(data.get("name"))
        elif step == "email":
            return bool(data.get("email_address"))
        elif step == "address":
            return all(
                [
                    data.get("address"),
                    isinstance(data.get("address"), dict),
                    data.get("address", {}).get("AddressLine1"),
                    data.get("address", {}).get("City"),
                    data.get("address", {}).get("PostalCode"),
                ]
            )
        # Non-voice steps can always advance
        return step in ["welcome", "review", "final_submit", "complete"]

    # Override parent's can_advance for backward compatibility
    def can_advance(self) -> bool:
        """Check if current step data is complete."""
        return self.validate_step_data(self.current_step, self.contact_data)

    def parse_contact_data(self, step: str, parsed_result: Any) -> dict[str, Any]:
        """Parse contact-specific data from voice input results."""
        data = {}

        if step == "name" and hasattr(parsed_result, "name"):
            data["name"] = parsed_result.name
        elif step == "email" and hasattr(parsed_result, "email_address"):
            data["email_address"] = parsed_result.email_address
        elif step == "address" and hasattr(parsed_result, "address_line1"):
            data["address"] = {
                "AddressLine1": parsed_result.address_line1,
                "City": parsed_result.city,
                "PostalCode": parsed_result.postal_code,
                "Country": parsed_result.country,
            }

        return data

    def store_step_result(self, step: str, result: BaseModel, transcript: str = ""):
        """Store the result of a step with validation."""
        self.transcripts[step] = transcript
        self.parsed_results[step] = result

        # Parse contact-specific data
        parsed_data = self.parse_contact_data(step, result)

        # Update contact_data and workflow_data
        self.contact_data.update(parsed_data)
        self.workflow_data.update(parsed_data)

        # Mark step as complete using parent's method
        if parsed_data:
            self.mark_step_complete(step, parsed_data)

        logger.info(f"Stored result for step {step}")

    # Step prompts are now defined as a class constant
    STEP_PROMPTS = {
        "welcome": "Welcome! Let's add a new contact. Press and hold to start.",
        "name": "Please say the contact's full name or organization name.",
        "email": "Please say the contact's email address.",
        "address": "Please say the full address including street, city, and postal code.",
        "review": "Review the contact details below. Click 'Confirm Details' to proceed.",
        "final_submit": "Ready to create this contact in Xero. Click 'Create Contact' to submit.",
        "complete": "Contact created successfully in Xero!",
    }

    def get_step_prompt(self) -> str:
        """Get the prompt for the current step."""
        return self.STEP_PROMPTS.get(self.current_step, "Unknown step")

    def to_contact_create(self) -> ContactCreate | None:
        """Convert session data to ContactCreate model."""
        if not all(
            [
                self.contact_data["name"],
                self.contact_data["email_address"],
                self.contact_data["address"],
            ]
        ):
            logger.warning("Cannot create ContactCreate - missing required data")
            return None

        try:
            return ContactCreate(
                Name=self.contact_data["name"],
                EmailAddress=self.contact_data["email_address"],
                Address=StreetAddress(**self.contact_data["address"]),
                DefaultCurrency="GBP",
            )
        except Exception as e:
            logger.error(f"Error creating ContactCreate model: {e}")
            return None

    def get_completed_steps(self) -> list[str]:
        """Get list of steps that have stored data."""
        # Use parent's completed_steps tracking
        return self.completed_steps

    def get_summary(self) -> dict:
        """Get a summary of collected contact data."""
        base_summary = self.to_dict()  # Use parent's serialization
        base_summary.update(
            {
                "contact_data": self.contact_data,
                "has_errors": bool(self.errors),
                "is_complete": self.current_step == "complete",
            }
        )
        return base_summary

    def update_field(self, field_name: str, field_value: str):
        """Update a single field in contact data."""
        # Handle address fields specially
        if field_name in ["address_line1", "city", "postal_code", "country"]:
            if self.contact_data["address"] is None:
                self.contact_data["address"] = {}
            # Map to Xero field names
            field_map = {
                "address_line1": "AddressLine1",
                "city": "City",
                "postal_code": "PostalCode",
                "country": "Country",
            }
            self.contact_data["address"][field_map.get(field_name, field_name)] = field_value
        else:
            # Handle simple fields (name, email_address)
            self.contact_data[field_name] = field_value

        self.updated_at = datetime.now(UTC)
        logger.info(f"Updated field {field_name} with value: {field_value}")

    def reset(self):
        """Reset the session to start over."""
        # Reset parent state
        self.current_step = self.get_initial_step()
        self.completed_steps = []
        self.workflow_data = {}
        self.step_errors = {}
        # Reset contact-specific state
        self.contact_data = {"name": None, "email_address": None, "address": None}
        self.transcripts = {}
        self.parsed_results = {}
        self.errors = {}
        self.updated_at = datetime.now(UTC)


# Session management functions
def get_contact_session(session_id: str | None = None) -> ContactWorkflowSession:
    """Get or create a contact workflow session."""
    if session_id and session_id in _sessions:
        session = _sessions[session_id]
        # Check if session is expired (30 minutes)
        if datetime.now(UTC) - session.updated_at > timedelta(minutes=30):
            logger.info(f"Session {session_id} expired, creating new session")
            del _sessions[session_id]
            session = ContactWorkflowSession(session_id)
            _sessions[session_id] = session
    else:
        session = ContactWorkflowSession(session_id)
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
