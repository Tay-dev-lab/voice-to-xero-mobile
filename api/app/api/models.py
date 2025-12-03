from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


# UK VAT categories hard-wired to Xero TaxType codes
class UKVat(str, Enum):
    STANDARD = "OUTPUT2"  # 20% VAT on income
    REDUCED = "REDUCED"  # 5% VAT on income
    ZERO_RATED = "ZERORATEDOUTPUT"  # 0% VAT (zero-rated supply)
    EXEMPT = "EXEMPTOUTPUT"  # VAT exempt


LineAmountType = Literal["Exclusive", "Inclusive"]


class LineItem(BaseModel):
    description: str
    quantity: Decimal = Field(..., gt=0)
    unit_amount: Decimal = Field(..., ge=0)
    account_code: str
    discount_rate: Decimal | None = Field(None, ge=0, le=100)
    vat: UKVat | None = None  # If not set, Xero will use the account's default tax


class InvoiceCreate(BaseModel):
    type: Literal["ACCREC"] = "ACCREC"
    status: Literal["AUTHORISED"] = "AUTHORISED"
    contact_id: UUID
    date: date
    due_date: date
    line_amount_type: LineAmountType = "Exclusive"
    line_items: list[LineItem] = Field(..., min_length=1)

    def to_xero_payload(self) -> dict:
        lines = []
        for li in self.line_items:
            line = {
                "Description": li.description,
                "Quantity": float(li.quantity),
                "UnitAmount": float(li.unit_amount),
                "AccountCode": li.account_code,
            }
            if li.discount_rate is not None:
                line["DiscountRate"] = float(li.discount_rate)
            if li.vat:
                line["TaxType"] = li.vat.value  # actual Xero code
            lines.append(line)

        return {
            "Invoices": [
                {
                    "Type": self.type,
                    "Status": self.status,
                    "Contact": {"ContactID": str(self.contact_id)},
                    "Date": self.date.isoformat(),
                    "DueDate": self.due_date.isoformat(),
                    "LineAmountTypes": self.line_amount_type,
                    "LineItems": lines,
                }
            ]
        }


class StreetAddress(BaseModel):
    AddressType: str = "STREET"  # Xero supports STREET or POBOX; we fix STREET
    AddressLine1: str = Field(..., min_length=1)
    City: str = Field(..., min_length=1)
    PostalCode: str = Field(..., min_length=1)
    Country: str = "GB"


class ContactCreate(BaseModel):
    Name: str  # required by Xero
    EmailAddress: EmailStr  # required by your spec
    Address: StreetAddress  # single STREET address
    DefaultCurrency: str = "GBP"  # UK orgs typically use GBP

    def to_xero_payload(self) -> dict:
        return {
            "Contacts": [
                {
                    "Name": self.Name,
                    "EmailAddress": self.EmailAddress,
                    "DefaultCurrency": self.DefaultCurrency,
                    "Addresses": [self.Address.model_dump()],
                }
            ]
        }
