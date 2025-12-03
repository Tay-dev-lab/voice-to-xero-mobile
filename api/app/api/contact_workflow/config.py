"""
Configuration for contact workflow.
Centralizes all configuration, prompts, and validation rules.
"""

from functools import lru_cache
from typing import Any

from app.api.workflow_base.config import BaseWorkflowConfig


class ContactWorkflowConfig(BaseWorkflowConfig):
    """Configuration specific to contact workflow."""

    # Override base settings
    app_name: str = "Contact Workflow"

    def get_workflow_steps(self) -> list[str]:
        """Return ordered list of workflow steps."""
        return ["welcome", "name", "email", "address", "review", "final_submit", "complete"]

    def get_step_prompts(self) -> dict[str, str]:
        """Return voice prompts for each step."""
        return {
            "welcome": "Welcome! Let's add a new contact. Click 'Start' to begin.",
            "name": "Please say the contact's full name or organization name.",
            "email": "Please say the contact's email address.",
            "address": "Please say the full address including street, city, and postal code.",
            "review": "Review the contact details below.",
            "final_submit": "Ready to create this contact in Xero.",
            "complete": "Contact created successfully!",
        }

    def get_step_titles(self) -> dict[str, str]:
        """Return display titles for steps."""
        return {
            "welcome": "Welcome",
            "name": "Contact Name",
            "email": "Email Address",
            "address": "Contact Address",
            "review": "Review Details",
            "final_submit": "Final Confirmation",
            "complete": "Complete",
        }

    def get_validation_rules(self) -> dict[str, Any]:
        """Return validation rules for contact fields."""
        return {
            "email": {
                "pattern": r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$",
                "message": "Please provide a valid email address",
            },
            "phone": {
                "pattern": r"^\+?[\d\s\-\(\)]+$",
                "min_length": 7,
                "max_length": 20,
                "message": "Please provide a valid phone number",
            },
            "name": {
                "min_length": 2,
                "max_length": 255,
                "message": "Name must be between 2 and 255 characters",
            },
            "address": {
                "required_fields": ["address_line1", "city", "postal_code"],
                "message": "Address must include street, city, and postal code",
            },
        }

    def get_rate_limits(self) -> dict[str, str]:
        """Return rate limiting configuration."""
        return {
            "voice_processing": "10/minute",
            "xero_submission": "5/minute",
            "step_navigation": "30/minute",
            "field_update": "20/minute",
        }

    def get_gpt_prompts(self) -> dict[str, str]:
        """Return GPT prompts for parsing voice input."""
        return {
            "name": """Extract the contact or organization name from the transcribed text.
Determine if this is an organization (company, LLC, Inc, Ltd, etc.) or individual person.
Be precise and preserve the exact name as spoken.""",
            "email": """Extract the email address from the transcribed text.
Common patterns: 'at' means @, 'dot' means .
Handle spelling like 'j o h n at example dot com' -> john@example.com
Return only the email address, nothing else.""",
            "address": """Extract the complete address from the transcribed text.
Parse into components: street address, city, state/region, postal code, country.
Default country to 'GB' if not specified.
Be intelligent about UK address formats.""",
        }

    def get_error_messages(self) -> dict[str, str]:
        """Return custom error messages for contact workflow."""
        base_messages = super().get_error_messages()
        base_messages.update(
            {
                "invalid_email": "Please provide a valid email address",
                "invalid_phone": "Please provide a valid phone number",
                "missing_name": "Contact name is required",
                "missing_address": "Please provide a complete address",
                "xero_error": "Failed to create contact in Xero. Please try again.",
                "duplicate_contact": "A contact with this email already exists",
            }
        )
        return base_messages


@lru_cache
def get_contact_config() -> ContactWorkflowConfig:
    """Get cached contact workflow configuration."""
    return ContactWorkflowConfig()
