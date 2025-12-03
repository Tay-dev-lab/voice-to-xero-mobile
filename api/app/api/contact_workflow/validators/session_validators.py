"""
Session and workflow state validators for contact workflow.
Handles validation of session state, step transitions, and workflow integrity.
"""

import logging
import re
from datetime import datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)


def validate_session_id(session_id: str) -> dict[str, Any]:
    """
    Validate session ID format and check expiry.

    Args:
        session_id: Session ID to validate

    Returns:
        Dict with validation result and details
    """
    result = {"is_valid": False, "error": None, "session_id": session_id}

    if not session_id:
        result["error"] = "Session ID is required"
        return result

    # UUID v4 format validation
    uuid_pattern = r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
    if not re.match(uuid_pattern, session_id.lower()):
        result["error"] = "Invalid session ID format"
        return result

    result["is_valid"] = True
    return result


def validate_step_transition(
    current_step: str, next_step: str, workflow_steps: list[str], completed_steps: list[str]
) -> dict[str, Any]:
    """
    Validate if transition from current step to next step is allowed.

    Args:
        current_step: Current workflow step
        next_step: Requested next step
        workflow_steps: Ordered list of all workflow steps
        completed_steps: List of completed steps

    Returns:
        Dict with validation result and details
    """
    result = {"is_valid": False, "error": None, "can_proceed": False}

    # Check if steps exist in workflow
    if current_step not in workflow_steps:
        result["error"] = f"Invalid current step: {current_step}"
        return result

    if next_step not in workflow_steps:
        result["error"] = f"Invalid next step: {next_step}"
        return result

    current_idx = workflow_steps.index(current_step)
    next_idx = workflow_steps.index(next_step)

    # Allow moving to the immediate next step
    if next_idx == current_idx + 1:
        result["is_valid"] = True
        result["can_proceed"] = True
        return result

    # Allow navigating back to completed steps
    if next_step in completed_steps:
        result["is_valid"] = True
        result["can_proceed"] = False  # Can go back but not proceed forward
        return result

    # Allow staying on current step
    if next_step == current_step:
        result["is_valid"] = True
        result["can_proceed"] = False
        return result

    result["error"] = f"Cannot transition from {current_step} to {next_step}"
    return result


def validate_workflow_state(session_data: dict[str, Any]) -> dict[str, Any]:
    """
    Validate overall workflow state integrity.

    Args:
        session_data: Complete session data

    Returns:
        Dict with validation result and any issues found
    """
    result = {"is_valid": True, "issues": [], "warnings": []}

    # Required session fields
    required_fields = ["session_id", "current_step", "created_at"]
    for field in required_fields:
        if field not in session_data:
            result["is_valid"] = False
            result["issues"].append(f"Missing required field: {field}")

    # Check session age (warn if older than 30 minutes)
    if "created_at" in session_data:
        try:
            created = datetime.fromisoformat(session_data["created_at"])
            age = datetime.utcnow() - created
            if age > timedelta(hours=1):
                result["warnings"].append("Session is over 1 hour old")
            if age > timedelta(hours=24):
                result["is_valid"] = False
                result["issues"].append("Session expired (over 24 hours old)")
        except (ValueError, TypeError):
            result["warnings"].append("Invalid created_at timestamp")

    # Validate completed steps are in correct order
    if "completed_steps" in session_data and "workflow_steps" in session_data:
        completed = session_data["completed_steps"]
        workflow = session_data["workflow_steps"]

        # Check that completed steps exist in workflow
        invalid_steps = [s for s in completed if s not in workflow]
        if invalid_steps:
            result["is_valid"] = False
            result["issues"].append(f"Invalid completed steps: {invalid_steps}")

    # Check for required data in completed steps
    if session_data.get("current_step") == "review":
        contact_data = session_data.get("contact_data", {})
        if not contact_data.get("name"):
            result["issues"].append("Missing contact name for review step")
        if not contact_data.get("email_address"):
            result["issues"].append("Missing email for review step")

    return result


def sanitize_step_name(step: str, valid_steps: list[str] | None = None) -> str:
    """
    Validate and sanitize workflow step name.

    Args:
        step: Step name
        valid_steps: List of valid step names (uses default if not provided)

    Returns:
        Validated step name

    Raises:
        ValueError: If step name is invalid
    """
    if valid_steps is None:
        valid_steps = ["welcome", "name", "email", "address", "review", "final_submit", "complete"]

    if step not in valid_steps:
        raise ValueError(f"Invalid step name: {step}")

    return step


def validate_step_completion(
    step: str, step_data: dict[str, Any], required_fields: dict[str, list[str]] | None = None
) -> dict[str, Any]:
    """
    Validate if a step has all required data for completion.

    Args:
        step: Step name
        step_data: Data collected for this step
        required_fields: Dict of step names to required field lists

    Returns:
        Dict with validation result and missing fields
    """
    result = {"is_complete": True, "missing_fields": [], "warnings": []}

    if required_fields is None:
        required_fields = {
            "name": ["name"],
            "email": ["email_address"],
            "address": ["address_line1", "city", "postal_code"],
        }

    # Check if step has required fields defined
    if step in required_fields:
        required = required_fields[step]
        missing = [f for f in required if not step_data.get(f)]

        if missing:
            result["is_complete"] = False
            result["missing_fields"] = missing

    # Additional validation for specific steps
    if step == "email" and step_data.get("email_address"):
        email = step_data["email_address"]
        if "@" not in email:
            result["warnings"].append("Email appears to be invalid")

    return result


def check_session_expiry(created_at: datetime, timeout_minutes: int = 30) -> bool:
    """
    Check if session has expired based on creation time.

    Args:
        created_at: Session creation timestamp
        timeout_minutes: Session timeout in minutes

    Returns:
        True if session has expired, False otherwise
    """
    age = datetime.utcnow() - created_at
    return age > timedelta(minutes=timeout_minutes)
