"""
Base models for workflow framework.
"""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel


class WorkflowStatus(str, Enum):
    """Workflow status enumeration."""

    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ERROR = "error"
    CANCELLED = "cancelled"


class BaseStepData(BaseModel):
    """Base model for step data."""

    step_name: str
    completed_at: datetime | None = None
    transcript: str | None = None

    class Config:
        extra = "allow"  # Allow additional fields


class WorkflowState(BaseModel):
    """Complete workflow state."""

    session_id: str
    workflow_name: str
    status: WorkflowStatus
    current_step: str
    completed_steps: list[str] = []
    workflow_data: dict[str, Any] = {}
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime


class StepValidationError(Exception):
    """Custom exception for step validation errors."""

    def __init__(self, field: str, message: str, partial_data: dict[str, Any] | None = None):
        self.field = field
        self.message = message
        self.partial_data = partial_data or {}
        super().__init__(self.message)


class WorkflowConfig(BaseModel):
    """Configuration for a workflow."""

    name: str
    steps: list[str]
    prompts: dict[str, str]
    validation_rules: dict[str, dict[str, Any]] = {}
    rate_limits: dict[str, str] = {}
    allow_skip: list[str] = []
    required_steps: list[str] = []
