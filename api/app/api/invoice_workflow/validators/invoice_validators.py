"""
Invoice-specific validators for line items and invoice data.
"""

import logging
from decimal import Decimal
from typing import Any

logger = logging.getLogger(__name__)


def validate_line_item(item: dict[str, Any]) -> dict[str, Any]:
    """
    Validate line item data completeness.

    Args:
        item: Dictionary containing line item data

    Returns:
        Dict with validation result and any errors found
    """
    errors = []

    # Check description
    if not item.get("description"):
        errors.append("Description is required")
    elif len(str(item.get("description", ""))) > 500:
        errors.append("Description must be less than 500 characters")

    # Check quantity
    quantity = item.get("quantity")
    if quantity is None:
        errors.append("Quantity is required")
    else:
        try:
            qty_decimal = Decimal(str(quantity))
            if qty_decimal <= 0:
                errors.append("Quantity must be greater than 0")
            if qty_decimal > 99999:
                errors.append("Quantity must be less than 100,000")
        except (ValueError, TypeError):
            errors.append("Quantity must be a valid number")

    # Check unit price
    price = item.get("unit_price")
    if price is None:
        errors.append("Unit price is required")
    else:
        try:
            price_decimal = Decimal(str(price))
            if price_decimal < 0:
                errors.append("Unit price must be non-negative")
            if price_decimal > 999999:
                errors.append("Unit price must be less than 1,000,000")
        except (ValueError, TypeError):
            errors.append("Unit price must be a valid number")

    # Check VAT rate
    vat_rate = item.get("vat_rate")
    valid_vat_rates = ["standard", "reduced", "zero_rated", "exempt"]
    if vat_rate and vat_rate not in valid_vat_rates:
        errors.append(f"Invalid VAT rate. Must be one of: {', '.join(valid_vat_rates)}")

    # Check account code (optional but validate if present)
    account_code = item.get("account_code")
    if account_code and not str(account_code).isdigit():
        errors.append("Account code must be numeric")

    return {"is_valid": len(errors) == 0, "errors": errors, "item": item}


def validate_invoice_completeness(invoice_data: dict[str, Any]) -> dict[str, Any]:
    """
    Check if invoice has all required data for Xero submission.

    Args:
        invoice_data: Dictionary containing all invoice data

    Returns:
        Dict with validation result and any issues found
    """
    issues = []
    warnings = []

    # Check contact name
    if not invoice_data.get("contact_name"):
        issues.append("Contact name is required")
    elif len(str(invoice_data.get("contact_name", ""))) > 255:
        issues.append("Contact name must be less than 255 characters")

    # Check due date
    if not invoice_data.get("due_date"):
        issues.append("Due date is required")
    else:
        # Could add date format validation here if needed
        pass

    # Check line items
    line_items = invoice_data.get("line_items", [])
    if not line_items:
        issues.append("At least one line item is required")
    elif len(line_items) > 10:
        issues.append("Maximum 10 line items allowed")
    else:
        # Validate each line item
        for idx, item in enumerate(line_items, 1):
            item_validation = validate_line_item(item)
            if not item_validation["is_valid"]:
                for error in item_validation["errors"]:
                    issues.append(f"Line item {idx}: {error}")

    # Calculate totals for warnings
    if line_items:
        total = sum(
            float(item.get("quantity", 0)) * float(item.get("unit_price", 0)) for item in line_items
        )
        if total > 100000:
            warnings.append("Invoice total exceeds £100,000")
        elif total == 0:
            warnings.append("Invoice total is £0")

    return {
        "is_valid": len(issues) == 0,
        "issues": issues,
        "warnings": warnings,
        "can_submit": len(issues) == 0,
    }


def calculate_line_item_totals(line_items: list[dict]) -> dict[str, float]:
    """
    Calculate subtotal, VAT, and grand total for line items.

    Args:
        line_items: List of line item dictionaries

    Returns:
        Dict with subtotal, vat_total, and grand_total
    """
    subtotal = 0.0
    vat_total = 0.0

    for item in line_items:
        quantity = float(item.get("quantity", 0))
        unit_price = float(item.get("unit_price", 0))
        item_total = quantity * unit_price
        subtotal += item_total

        # Calculate VAT based on rate
        vat_rate = item.get("vat_rate", "standard")
        if vat_rate == "standard":
            vat_total += item_total * 0.20
        elif vat_rate == "reduced":
            vat_total += item_total * 0.05
        # zero_rated and exempt have 0 VAT

    return {
        "subtotal": round(subtotal, 2),
        "vat_total": round(vat_total, 2),
        "grand_total": round(subtotal + vat_total, 2),
    }


def validate_vat_rate(vat_rate: str) -> bool:
    """
    Validate that VAT rate is one of the allowed values.

    Args:
        vat_rate: VAT rate string to validate

    Returns:
        True if valid, False otherwise
    """
    valid_rates = ["standard", "reduced", "zero_rated", "exempt"]
    return vat_rate in valid_rates


def format_vat_rate_display(vat_rate: str) -> str:
    """
    Format VAT rate for user-friendly display.

    Args:
        vat_rate: Internal VAT rate code

    Returns:
        Formatted display string
    """
    display_names = {
        "standard": "Standard Rate (20%)",
        "reduced": "Reduced Rate (5%)",
        "zero_rated": "Zero Rated (0%)",
        "exempt": "VAT Exempt",
    }
    return display_names.get(vat_rate, vat_rate.replace("_", " ").title())
