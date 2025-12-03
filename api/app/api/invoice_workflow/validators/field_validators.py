"""
Field-level validators for contact workflow.
Handles validation and sanitization of individual contact fields.
"""

import html
import logging
import re

logger = logging.getLogger(__name__)


def sanitize_html(text: str) -> str:
    """Escape HTML special characters to prevent XSS attacks."""
    if not text:
        return ""
    return html.escape(str(text), quote=True)


def sanitize_name(name: str) -> str:
    """
    Sanitize contact/organization name.

    Args:
        name: Raw name input

    Returns:
        Sanitized name

    Raises:
        ValueError: If name is invalid
    """
    if not name or not name.strip():
        raise ValueError("Name cannot be empty")

    # Remove excessive whitespace
    name = " ".join(name.split())

    # Limit length
    if len(name) > 255:
        raise ValueError("Name cannot exceed 255 characters")

    # Remove potentially dangerous characters but allow common name chars
    # Allow letters, numbers, spaces, hyphens, apostrophes, periods, commas
    allowed_pattern = r"^[a-zA-Z0-9\s\-'.,&]+$"
    if not re.match(allowed_pattern, name):
        raise ValueError(
            "Name contains invalid characters. Only letters, numbers, spaces, "
            "hyphens, apostrophes, periods, commas, and ampersands are allowed."
        )

    return name


def sanitize_email(email: str) -> str:
    """
    Validate and sanitize email address.

    Args:
        email: Raw email input

    Returns:
        Validated email address

    Raises:
        ValueError: If email is invalid
    """
    if not email or not email.strip():
        raise ValueError("Email cannot be empty")

    # Convert to lowercase and strip whitespace
    email = email.lower().strip()

    # Basic email validation regex
    email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    if not re.match(email_pattern, email):
        raise ValueError("Invalid email address format")

    # Additional validation for common issues
    if email.count("@") != 1:
        raise ValueError("Email must contain exactly one @ symbol")

    if ".." in email:
        raise ValueError("Email cannot contain consecutive dots")

    if email.startswith(".") or email.endswith("."):
        raise ValueError("Email cannot start or end with a dot")

    # Limit length
    if len(email) > 254:
        raise ValueError("Email address too long")

    return email


def sanitize_phone(phone: str) -> str | None:
    """
    Sanitize phone number (optional field).

    Args:
        phone: Raw phone input

    Returns:
        Sanitized phone number or None

    Raises:
        ValueError: If phone format is invalid
    """
    if not phone or not phone.strip():
        return None

    # Remove common formatting characters
    phone = phone.strip()

    # Validate format (allow digits, spaces, hyphens, parentheses, plus)
    phone_pattern = r"^\+?[\d\s\-\(\)]+$"
    if not re.match(phone_pattern, phone):
        raise ValueError("Invalid phone number format")

    # Check minimum and maximum length
    digits_only = re.sub(r"\D", "", phone)
    if len(digits_only) < 7:
        raise ValueError("Phone number too short")
    if len(digits_only) > 20:
        raise ValueError("Phone number too long")

    return phone


def sanitize_address_line(address: str) -> str:
    """
    Sanitize street address line.

    Args:
        address: Raw address input

    Returns:
        Sanitized address

    Raises:
        ValueError: If address is invalid
    """
    if not address or not address.strip():
        raise ValueError("Address cannot be empty")

    # Remove excessive whitespace
    address = " ".join(address.split())

    # Limit length
    if len(address) > 500:
        raise ValueError("Address cannot exceed 500 characters")

    # Allow letters, numbers, spaces, and common address punctuation
    allowed_pattern = r"^[a-zA-Z0-9\s\-'.,#/]+$"
    if not re.match(allowed_pattern, address):
        raise ValueError(
            "Address contains invalid characters. Only letters, numbers, spaces, "
            "hyphens, apostrophes, periods, commas, hash, and forward slash are allowed."
        )

    return address


def sanitize_city(city: str) -> str:
    """
    Sanitize city name.

    Args:
        city: Raw city input

    Returns:
        Sanitized city name

    Raises:
        ValueError: If city is invalid
    """
    if not city or not city.strip():
        raise ValueError("City cannot be empty")

    # Remove excessive whitespace
    city = " ".join(city.split())

    # Limit length
    if len(city) > 100:
        raise ValueError("City name cannot exceed 100 characters")

    # Allow letters, spaces, hyphens, apostrophes, periods (for St. etc)
    allowed_pattern = r"^[a-zA-Z\s\-'.]+$"
    if not re.match(allowed_pattern, city):
        raise ValueError(
            "City name contains invalid characters. Only letters, spaces, "
            "hyphens, apostrophes, and periods are allowed."
        )

    return city


def sanitize_postal_code(postal_code: str) -> str:
    """
    Sanitize postal/ZIP code.

    Args:
        postal_code: Raw postal code input

    Returns:
        Sanitized postal code

    Raises:
        ValueError: If postal code is invalid
    """
    if not postal_code or not postal_code.strip():
        raise ValueError("Postal code cannot be empty")

    # Remove whitespace for validation (UK postcodes have internal spaces)
    postal_code = postal_code.strip().upper()

    # Limit length
    if len(postal_code) > 20:
        raise ValueError("Postal code cannot exceed 20 characters")

    # Allow letters, numbers, spaces, and hyphens (covers most formats)
    allowed_pattern = r"^[A-Z0-9\s\-]+$"
    if not re.match(allowed_pattern, postal_code):
        raise ValueError(
            "Postal code contains invalid characters. Only letters, numbers, "
            "spaces, and hyphens are allowed."
        )

    return postal_code


def sanitize_country_code(country: str) -> str:
    """
    Validate country code (ISO 3166-1 alpha-2).

    Args:
        country: Country code

    Returns:
        Validated country code in uppercase

    Raises:
        ValueError: If country code is invalid
    """
    if not country or not country.strip():
        # Default to GB if not provided
        return "GB"

    country = country.strip().upper()

    # Must be exactly 2 uppercase letters
    if not re.match(r"^[A-Z]{2}$", country):
        raise ValueError("Country code must be 2 letters (e.g., GB, US)")

    # Common country codes validation (not exhaustive)
    common_codes = {
        "GB",
        "US",
        "CA",
        "AU",
        "NZ",
        "IE",
        "FR",
        "DE",
        "ES",
        "IT",
        "NL",
        "BE",
        "CH",
        "AT",
        "SE",
        "NO",
        "DK",
        "FI",
        "PL",
        "CZ",
    }

    if country not in common_codes:
        # Allow but log warning for uncommon codes
        logger.warning(f"Uncommon country code used: {country}")

    return country
