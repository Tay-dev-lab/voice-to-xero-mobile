"""
Abstract base class for workflow sessions.
"""

import uuid
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import Any


class BaseWorkflowSession(ABC):
    """Abstract base class for workflow sessions."""

    def __init__(self, session_id: str | None = None):
        """Initialize base workflow session."""
        self.session_id = session_id or str(uuid.uuid4())
        self.current_step = self.get_initial_step()
        self.completed_steps: list[str] = []
        self.workflow_data: dict[str, Any] = {}
        self.step_errors: dict[str, str] = {}
        self.created_at = datetime.now(UTC)
        self.updated_at = datetime.now(UTC)

    @abstractmethod
    def get_workflow_steps(self) -> list[str]:
        """Return ordered list of workflow steps."""

    @abstractmethod
    def get_initial_step(self) -> str:
        """Return the first step of the workflow."""

    @abstractmethod
    def validate_step_data(self, step: str, data: dict[str, Any]) -> bool:
        """Validate data for a specific step."""

    def advance_step(self) -> str | None:
        """Move to next step in workflow."""
        steps = self.get_workflow_steps()
        current_idx = steps.index(self.current_step)

        if current_idx < len(steps) - 1:
            self.current_step = steps[current_idx + 1]
            self.updated_at = datetime.now(UTC)
            return self.current_step
        return None

    def can_advance(self) -> bool:
        """Check if workflow can advance to next step."""
        # Must have completed current step
        if self.current_step not in self.completed_steps:
            return False

        # Check for required data
        return self.validate_step_data(self.current_step, self.workflow_data)

    def go_to_step(self, step: str) -> bool:
        """Navigate to a specific step if allowed."""
        steps = self.get_workflow_steps()

        if step not in steps:
            return False

        # Can only go to completed steps or next step
        target_idx = steps.index(step)

        if target_idx <= len(self.completed_steps):
            self.current_step = step
            self.updated_at = datetime.now(UTC)
            return True

        return False

    def mark_step_complete(self, step: str, data: dict[str, Any]):
        """Mark a step as completed with its data."""
        if step not in self.completed_steps:
            self.completed_steps.append(step)

        self.workflow_data.update(data)
        self.updated_at = datetime.now(UTC)

        # Clear any errors for this step
        self.step_errors.pop(step, None)

    def get_progress_percentage(self) -> float:
        """Calculate workflow completion percentage."""
        total_steps = len(self.get_workflow_steps())
        completed = len(self.completed_steps)
        return (completed / total_steps) * 100 if total_steps > 0 else 0

    def to_dict(self) -> dict[str, Any]:
        """Serialize session to dictionary."""
        return {
            "session_id": self.session_id,
            "current_step": self.current_step,
            "completed_steps": self.completed_steps,
            "workflow_data": self.workflow_data,
            "step_errors": self.step_errors,
            "progress": self.get_progress_percentage(),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
