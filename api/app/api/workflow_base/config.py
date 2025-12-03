"""
Base configuration class for workflow system.
Provides abstract interface for workflow-specific configurations.
"""

from abc import ABC, abstractmethod
from functools import lru_cache
from typing import Any

from pydantic_settings import BaseSettings


class BaseWorkflowConfig(ABC, BaseSettings):
    """Abstract base class for workflow configuration."""

    # Common configuration that all workflows can override
    app_name: str = "Workflow System"
    debug: bool = False
    session_timeout_minutes: int = 30
    max_file_upload_size: int = 10 * 1024 * 1024  # 10MB

    @abstractmethod
    def get_workflow_steps(self) -> list[str]:
        """Return ordered list of workflow steps."""

    @abstractmethod
    def get_step_prompts(self) -> dict[str, str]:
        """Return prompts for each step."""

    @abstractmethod
    def get_validation_rules(self) -> dict[str, Any]:
        """Return validation rules for fields."""

    @abstractmethod
    def get_rate_limits(self) -> dict[str, str]:
        """Return rate limiting configuration."""

    def get_step_titles(self) -> dict[str, str]:
        """Return display titles for steps (can be overridden)."""
        steps = self.get_workflow_steps()
        return {step: step.replace("_", " ").title() for step in steps}

    def get_error_messages(self) -> dict[str, str]:
        """Return custom error messages (can be overridden)."""
        return {
            "session_expired": "Your session has expired. Please start over.",
            "validation_failed": "Please check your input and try again.",
            "rate_limit": "Too many requests. Please wait a moment.",
            "server_error": "An unexpected error occurred. Please try again.",
        }

    class Config:
        env_file = ".env"
        env_prefix = "WORKFLOW_"
        case_sensitive = False


@lru_cache
def get_base_config() -> BaseWorkflowConfig:
    """Get cached base configuration (to be overridden by specific workflows)."""
    raise NotImplementedError("Must use a specific workflow configuration")
