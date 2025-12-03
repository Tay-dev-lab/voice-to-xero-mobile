"""
Pydantic models for contact workflow steps.
"""

from pydantic import BaseModel, EmailStr, Field


class ContactNameStep(BaseModel):
    """Step 1: Parse contact/organization name from voice input."""

    name: str = Field(..., min_length=1, description="Full name or organization name")
    is_organization: bool = Field(default=False, description="Whether this is an organization")


class ContactEmailStep(BaseModel):
    """Step 2: Parse email address from voice input."""

    email_address: EmailStr = Field(..., description="Valid email address")


class ContactAddressStep(BaseModel):
    """Step 3: Parse full address from voice input."""

    address_line1: str = Field(..., min_length=1, description="Street address")
    city: str = Field(..., min_length=1, description="City name")
    postal_code: str = Field(..., min_length=1, description="Postal/ZIP code")
    country: str = Field(default="GB", description="Country code")


class ContactConfirmation(BaseModel):
    """Step 4: Parse confirmation response from voice input."""

    confirmed: bool = Field(..., description="Whether user confirmed the details")
    corrections_needed: str | None = Field(None, description="Any corrections mentioned")


class StepValidationError(Exception):
    """Custom exception for step validation with user-friendly messages."""

    def __init__(self, field: str, message: str, partial_data: dict | None = None):
        self.field = field
        self.message = message
        self.partial_data = partial_data or {}
        super().__init__(message)
