"""
Pydantic models for invoice workflow steps.
"""

from datetime import date
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, Field


# User-friendly VAT mapping
class VATRate(str, Enum):
    """User-friendly VAT rate names that map to Xero tax codes."""

    STANDARD = "standard"  # Maps to OUTPUT2 (20%)
    REDUCED = "reduced"  # Maps to REDUCED (5%)
    ZERO_RATED = "zero_rated"  # Maps to ZERORATEDOUTPUT (0%)
    EXEMPT = "exempt"  # Maps to EXEMPTOUTPUT

    def to_xero_code(self) -> str:
        """Convert user-friendly VAT rate to Xero tax code."""
        mapping = {
            "standard": "OUTPUT2",
            "reduced": "REDUCED",
            "zero_rated": "ZERORATEDOUTPUT",
            "exempt": "EXEMPTOUTPUT",
        }
        return mapping[self.value]


class InvoiceContactNameStep(BaseModel):
    """Parse contact/organization name from voice input."""

    contact_name: str = Field(..., min_length=1, description="Contact or organization name")
    is_organization: bool = Field(default=False, description="Whether this is an organization")


class InvoiceDueDateStep(BaseModel):
    """Parse due date from voice input."""

    due_date: date = Field(..., description="Invoice due date")
    days_from_now: int | None = Field(None, description="Days from today (for relative dates)")


class InvoiceLineItemStep(BaseModel):
    """Parse line item details from voice input."""

    description: str = Field(..., min_length=1, description="Line item description")
    quantity: Decimal = Field(..., gt=0, description="Quantity")
    unit_price: Decimal = Field(..., ge=0, description="Unit price")
    account_code: str = Field(default="200", description="Account code (default: 200 for sales)")
    vat_rate: VATRate = Field(default=VATRate.STANDARD, description="VAT rate")


class StepValidationError(Exception):
    """Custom exception for step validation with user-friendly messages."""

    def __init__(self, field: str, message: str, partial_data: dict | None = None):
        self.field = field
        self.message = message
        self.partial_data = partial_data or {}
        super().__init__(message)
