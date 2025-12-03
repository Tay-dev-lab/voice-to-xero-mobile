"""
Pydantic schemas for API responses.

These schemas define the structure of JSON responses for the mobile API.
"""

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ErrorDetail(BaseModel):
    """Structured error detail for API responses."""

    code: str = Field(..., description="Error code (e.g., 'VALIDATION_ERROR')")
    message: str = Field(..., description="Human-readable error message")
    field: str | None = Field(None, description="Field name for validation errors")
    details: dict[str, Any] | None = Field(None, description="Additional error context")


class APIResponse(BaseModel, Generic[T]):
    """Standard API response envelope for mobile clients."""

    success: bool
    data: T | None = None
    error: ErrorDetail | None = None


# Auth response schemas
class AuthStatusData(BaseModel):
    """Auth status response data."""

    xero_connected: bool
    openai_valid: bool
    ready_for_operations: bool
    tenant_id: str | None = None


class OpenAIValidationData(BaseModel):
    """OpenAI key validation response data."""

    valid: bool
    message: str


class MobileTokenData(BaseModel):
    """Mobile JWT token response data."""

    token: str
    expires_in: int = Field(default=86400, description="Token expiry in seconds")
    token_type: str = Field(default="Bearer")


# Workflow response schemas
class WorkflowInitData(BaseModel):
    """Workflow initialization response data."""

    session_id: str
    current_step: str
    step_prompt: str
    workflow_steps: list[str]
    completed_steps: list[str]
    csrf_token: str | None = None


class StepProcessData(BaseModel):
    """Step processing response data."""

    step: str
    transcript: str
    parsed_data: dict[str, Any]
    requires_confirmation: bool = True
    next_step: str | None = None
    session_id: str
    completed_steps: list[str]


class StepConfirmData(BaseModel):
    """Step confirmation response data."""

    confirmed_step: str
    current_step: str
    step_prompt: str
    completed_steps: list[str]


class FieldUpdateData(BaseModel):
    """Field update response data."""

    field: str
    value: str
    updated: bool


# Contact-specific schemas
class ContactSummaryData(BaseModel):
    """Contact summary response data."""

    name: str | None = None
    is_organization: bool = False
    email_address: str | None = None
    address_line1: str | None = None
    city: str | None = None
    postal_code: str | None = None
    country: str = "GB"
    is_complete: bool = False
    editable_fields: list[str] = Field(default_factory=list)


class ContactSubmitData(BaseModel):
    """Contact submission response data."""

    contact_id: str
    xero_contact_id: str | None = None
    name: str
    email: str | None = None


# Invoice-specific schemas
class LineItemData(BaseModel):
    """Invoice line item data."""

    description: str
    quantity: float
    unit_price: float
    vat_rate: str = "standard"
    line_total: float


class InvoiceSummaryData(BaseModel):
    """Invoice summary response data."""

    contact_name: str | None = None
    contact_id: str | None = None
    due_date: str | None = None
    line_items: list[LineItemData] = Field(default_factory=list)
    subtotal: float = 0.0
    vat_total: float = 0.0
    grand_total: float = 0.0
    is_complete: bool = False
    editable_fields: list[str] = Field(default_factory=list)


class LineItemConfirmData(BaseModel):
    """Line item confirmation response data."""

    line_items: list[LineItemData]
    item_count: int
    can_add_more: bool = True
    max_items: int = 10


class InvoiceSubmitData(BaseModel):
    """Invoice submission response data."""

    invoice_id: str
    xero_invoice_id: str | None = None
    invoice_number: str | None = None
    contact_name: str
    total: float
    status: str = "AUTHORISED"


# Error code constants
class ErrorCodes:
    """Standard error codes for API responses."""

    # Authentication
    AUTH_REQUIRED = "AUTH_REQUIRED"
    AUTH_EXPIRED = "AUTH_EXPIRED"
    INVALID_TOKEN = "INVALID_TOKEN"
    XERO_NOT_CONNECTED = "XERO_NOT_CONNECTED"
    OPENAI_NOT_VALID = "OPENAI_NOT_VALID"

    # Session
    SESSION_EXPIRED = "SESSION_EXPIRED"
    SESSION_INVALID = "SESSION_INVALID"
    SESSION_NOT_FOUND = "SESSION_NOT_FOUND"

    # Validation
    VALIDATION_ERROR = "VALIDATION_ERROR"
    MISSING_FIELD = "MISSING_FIELD"

    # Workflow
    INVALID_STEP = "INVALID_STEP"
    STEP_INCOMPLETE = "STEP_INCOMPLETE"
    WORKFLOW_ERROR = "WORKFLOW_ERROR"

    # Xero
    XERO_ERROR = "XERO_ERROR"
    XERO_AUTH_FAILED = "XERO_AUTH_FAILED"

    # Voice processing
    TRANSCRIPTION_FAILED = "TRANSCRIPTION_FAILED"
    PARSING_FAILED = "PARSING_FAILED"
    AUDIO_ERROR = "AUDIO_ERROR"
