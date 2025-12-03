"""
Custom exceptions for workflow system.
Provides a hierarchy of exceptions for better error handling.
"""

from typing import Any


class WorkflowException(Exception):
    """Base exception for all workflow-related errors."""

    def __init__(
        self,
        message: str,
        step: str | None = None,
        details: dict[str, Any] | None = None,
        user_message: str | None = None,
    ):
        """
        Initialize workflow exception.

        Args:
            message: Technical error message for logging
            step: Workflow step where error occurred
            details: Additional error details
            user_message: User-friendly message to display
        """
        self.message = message
        self.step = step
        self.details = details or {}
        self.user_message = user_message or "An error occurred. Please try again."
        super().__init__(self.message)

    def to_dict(self) -> dict[str, Any]:
        """Convert exception to dictionary for API responses."""
        return {
            "error": self.__class__.__name__,
            "message": self.user_message,
            "step": self.step,
            "details": self.details,
        }


class SessionException(WorkflowException):
    """Base exception for session-related errors."""


class SessionExpiredException(SessionException):
    """Raised when a session has expired."""

    def __init__(self, session_id: str):
        super().__init__(
            message=f"Session {session_id} has expired",
            user_message="Your session has expired. Please start over.",
            details={"session_id": session_id},
        )


class SessionNotFoundException(SessionException):
    """Raised when a session cannot be found."""

    def __init__(self, session_id: str):
        super().__init__(
            message=f"Session {session_id} not found",
            user_message="Session not found. Please start a new session.",
            details={"session_id": session_id},
        )


class StepValidationException(WorkflowException):
    """Raised when step validation fails."""

    def __init__(self, step: str, field: str | None = None, validation_error: str | None = None):
        super().__init__(
            message=f"Validation failed for step {step}",
            step=step,
            user_message=validation_error or "Please check your input and try again.",
            details={"field": field, "validation_error": validation_error},
        )


class VoiceProcessingException(WorkflowException):
    """Raised when voice processing fails."""

    def __init__(
        self, step: str, error_type: str = "transcription", original_error: str | None = None
    ):
        messages = {
            "transcription": "Could not understand audio. Please speak clearly and try again.",
            "parsing": "Could not parse the information. Please try again.",
            "timeout": "Audio processing timed out. Please try again.",
            "file_error": "Audio file error. Please record again.",
        }

        super().__init__(
            message=f"Voice processing failed at {step}: {error_type}",
            step=step,
            user_message=messages.get(error_type, "Voice processing failed. Please try again."),
            details={"error_type": error_type, "original_error": original_error},
        )


class ExternalServiceException(WorkflowException):
    """Base exception for external service errors."""

    def __init__(
        self,
        service: str,
        message: str,
        status_code: int | None = None,
        response: dict | None = None,
    ):
        super().__init__(
            message=f"{service} error: {message}",
            user_message=f"Service error: {service}. Please try again later.",
            details={"service": service, "status_code": status_code, "response": response},
        )
        self.service = service
        self.status_code = status_code


class XeroException(ExternalServiceException):
    """Raised when Xero API operations fail."""

    def __init__(
        self,
        operation: str,
        error_message: str,
        status_code: int | None = None,
        xero_error: dict | None = None,
    ):
        super().__init__(
            service="Xero",
            message=f"Xero {operation} failed: {error_message}",
            status_code=status_code,
            response=xero_error,
        )
        self.operation = operation


class RateLimitException(WorkflowException):
    """Raised when rate limit is exceeded."""

    def __init__(self, endpoint: str, limit: str, retry_after: int | None = None):
        super().__init__(
            message=f"Rate limit exceeded for {endpoint}",
            user_message="Too many requests. Please wait a moment and try again.",
            details={"endpoint": endpoint, "limit": limit, "retry_after": retry_after},
        )
        self.retry_after = retry_after
