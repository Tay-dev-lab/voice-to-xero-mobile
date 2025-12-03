"""
Common parsing utilities for workflow steps.
Provides reusable parsing functions for voice input processing.
"""

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


def parse_name(text: str) -> dict[str, Any]:
    """
    Parse name from text, detect if organization.

    Args:
        text: Input text containing a name

    Returns:
        Dict with name and is_organization flag
    """
    text = text.strip()

    # Check for organization indicators
    org_indicators = [
        "company",
        "llc",
        "inc",
        "ltd",
        "limited",
        "corporation",
        "corp",
        "plc",
        "gmbh",
        "partners",
        "partnership",
        "associates",
    ]

    is_org = any(indicator in text.lower() for indicator in org_indicators)

    # Clean up common speech patterns
    text = re.sub(r"\b(the|my|our)\s+", "", text, flags=re.IGNORECASE)

    return {"name": text.strip(), "is_organization": is_org}


def parse_email(text: str) -> str | None:
    """
    Extract email from text, handling common speech patterns.

    Args:
        text: Input text containing an email

    Returns:
        Extracted email address or None
    """
    # Handle common speech patterns for email
    text = text.lower().strip()

    # Replace spoken patterns
    replacements = {
        " at ": "@",
        " dot ": ".",
        " dash ": "-",
        " underscore ": "_",
        "at symbol": "@",
        "period": ".",
    }

    for spoken, symbol in replacements.items():
        text = text.replace(spoken, symbol)

    # Remove spaces around @ and .
    text = re.sub(r"\s*@\s*", "@", text)
    text = re.sub(r"\s*\.\s*", ".", text)

    # Find email pattern
    email_pattern = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
    matches = re.findall(email_pattern, text)

    if matches:
        return matches[0]

    # Try to construct email if pattern not found but has @
    if "@" in text:
        # Remove extra spaces
        text = "".join(text.split())
        if re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", text):
            return text

    return None


def parse_phone(text: str) -> str | None:
    """
    Extract phone number from text.

    Args:
        text: Input text containing a phone number

    Returns:
        Extracted phone number or None
    """
    # Remove common words
    text = re.sub(r"\b(phone|number|my|is|the)\b", "", text, flags=re.IGNORECASE)

    # Extract digits and common separators
    phone_pattern = r"[\d\s\-\(\)\+]+"
    matches = re.findall(phone_pattern, text)

    if matches:
        phone = "".join(matches).strip()
        # Verify minimum digits
        digits = re.sub(r"\D", "", phone)
        if len(digits) >= 7:
            return phone

    return None


def parse_address(text: str) -> dict[str, Any]:
    """
    Parse address components from text.

    Args:
        text: Input text containing an address

    Returns:
        Dict with address components
    """
    # Initialize result
    result = {
        "address_line1": "",
        "address_line2": "",
        "city": "",
        "region": "",
        "postal_code": "",
        "country": "GB",  # Default
    }

    # Look for postal code patterns
    # UK postal code
    uk_postcode = re.search(r"\b[A-Z]{1,2}\d{1,2}[A-Z]?\s*\d[A-Z]{2}\b", text.upper())
    if uk_postcode:
        result["postal_code"] = uk_postcode.group()
        text = text[: uk_postcode.start()] + text[uk_postcode.end() :]

    # US ZIP code
    us_zip = re.search(r"\b\d{5}(-\d{4})?\b", text)
    if not result["postal_code"] and us_zip:
        result["postal_code"] = us_zip.group()
        result["country"] = "US"
        text = text[: us_zip.start()] + text[us_zip.end() :]

    # Split by common delimiters
    parts = re.split(r"[,\n]", text)
    parts = [p.strip() for p in parts if p.strip()]

    if parts:
        # First part is usually street address
        result["address_line1"] = parts[0]

        # Try to identify city (usually second to last or before postal code)
        if len(parts) > 1:
            # Look for city names (capitalized words)
            for i, part in enumerate(parts[1:], 1):
                # Simple heuristic: if it's mostly letters and spaces, might be city
                if re.match(r"^[A-Za-z\s\-\']+$", part):
                    result["city"] = part
                    break

        # Remaining parts might be address line 2 or region
        remaining = [p for p in parts[1:] if p != result["city"]]
        if remaining:
            result["address_line2"] = remaining[0] if len(remaining) > 0 else ""

    return result


def extract_field_value(
    text: str, field_type: str, patterns: dict[str, str] | None = None
) -> Any | None:
    """
    Generic field extraction based on type.

    Args:
        text: Input text
        field_type: Type of field to extract
        patterns: Optional custom patterns

    Returns:
        Extracted value or None
    """
    if field_type == "email":
        return parse_email(text)
    elif field_type == "phone":
        return parse_phone(text)
    elif field_type == "name":
        result = parse_name(text)
        return result["name"]
    elif field_type == "address":
        return parse_address(text)

    # Custom pattern matching
    if patterns and field_type in patterns:
        pattern = patterns[field_type]
        match = re.search(pattern, text)
        if match:
            return match.group(1) if match.groups() else match.group()

    return None


def clean_transcript(transcript: str) -> str:
    """
    Clean up common speech recognition artifacts.

    Args:
        transcript: Raw transcript from speech recognition

    Returns:
        Cleaned transcript
    """
    # Remove filler words
    filler_words = ["um", "uh", "er", "ah", "like", "you know", "so"]
    for filler in filler_words:
        transcript = re.sub(rf"\b{filler}\b", "", transcript, flags=re.IGNORECASE)

    # Remove extra whitespace
    transcript = " ".join(transcript.split())

    # Fix common recognition errors
    corrections = {
        "add symbol": "@",
        "hashtag": "#",
        "ampersand": "&",
    }

    for wrong, right in corrections.items():
        transcript = transcript.replace(wrong, right)

    return transcript.strip()
