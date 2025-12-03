"""
Xero API service for creating invoices.
"""

import logging
from typing import Any
from urllib.parse import quote

import httpx

logger = logging.getLogger(__name__)


def map_vat_rate(vat_rate: str) -> str:
    """
    Map VAT rate string to Xero TaxType code.

    Args:
        vat_rate: VAT rate string from session (e.g., "standard", "reduced")

    Returns:
        Xero TaxType code
    """
    mapping = {
        "standard": "OUTPUT2",  # 20% UK VAT on income
        "reduced": "REDUCED",  # 5% UK VAT
        "zero_rated": "ZERORATEDOUTPUT",  # 0% VAT (zero-rated supply)
        "exempt": "EXEMPTOUTPUT",  # VAT exempt
    }
    return mapping.get(vat_rate, "OUTPUT2")


async def find_contact_by_name(
    contact_name: str,
    access_token: str,
    xero_tenant_id: str,
) -> str | None:
    """
    Search for an existing contact by name in Xero.

    Args:
        contact_name: Name to search for
        access_token: Xero OAuth2 access token
        xero_tenant_id: Xero tenant ID

    Returns:
        ContactID if found, None otherwise
    """
    try:
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Xero-Tenant-Id": xero_tenant_id,
            "Accept": "application/json",
        }

        # URL encode the contact name for the where clause
        # Xero uses OData-style filtering
        where_clause = f'Name=="{contact_name}"'
        encoded_where = quote(where_clause)

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://api.xero.com/api.xro/2.0/Contacts?where={encoded_where}",
                headers=headers,
                timeout=30.0,
            )

            logger.info(f"Xero contact search response: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                contacts = data.get("Contacts", [])
                if contacts:
                    contact_id = contacts[0].get("ContactID")
                    logger.info(f"Found existing contact '{contact_name}' with ID: {contact_id}")
                    return contact_id
                logger.info(f"No existing contact found for name: {contact_name}")
                return None
            else:
                logger.warning(f"Contact search failed: {response.status_code} - {response.text}")
                return None

    except Exception as e:
        logger.error(f"Error searching for contact: {e}")
        return None


async def create_contact_for_invoice(
    contact_name: str,
    access_token: str,
    xero_tenant_id: str,
) -> str | None:
    """
    Create a minimal contact in Xero for linking to an invoice.

    Args:
        contact_name: Name for the new contact
        access_token: Xero OAuth2 access token
        xero_tenant_id: Xero tenant ID

    Returns:
        ContactID of created contact, or None if failed
    """
    try:
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Xero-Tenant-Id": xero_tenant_id,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        # Minimal contact - just the name (required field)
        request_body = {
            "Contacts": [
                {
                    "Name": contact_name,
                    "IsCustomer": True,
                }
            ]
        }

        logger.info(f"Creating contact in Xero: {contact_name}")

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.xero.com/api.xro/2.0/Contacts",
                headers=headers,
                json=request_body,
                timeout=30.0,
            )

            logger.info(f"Xero create contact response: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                contacts = data.get("Contacts", [])
                if contacts:
                    contact_id = contacts[0].get("ContactID")
                    logger.info(f"Created contact '{contact_name}' with ID: {contact_id}")
                    return contact_id
                logger.error("No contact returned in create response")
                return None
            else:
                logger.error(f"Failed to create contact: {response.status_code} - {response.text}")
                return None

    except Exception as e:
        logger.error(f"Error creating contact: {e}")
        return None


async def create_xero_invoice(
    contact_name: str,
    due_date: str,
    line_items: list[dict],
    access_token: str,
    xero_tenant_id: str,
    contact_id: str | None = None,
    send_email: bool = True,
) -> dict[str, Any] | None:
    """
    Create an invoice in Xero.

    This function will:
    1. Use provided contact_id, or search for existing contact by name
    2. Create a new contact if not found
    3. Create the invoice as AUTHORISED (ready to send)
    4. Get online invoice URL and send email if requested

    Args:
        contact_name: Name of the contact for the invoice
        due_date: Due date in ISO format (YYYY-MM-DD)
        line_items: List of line item dicts with description, quantity, unit_price, vat_rate
        access_token: Xero OAuth2 access token
        xero_tenant_id: Xero tenant ID
        contact_id: Optional ContactID if already known (from dropdown selection)
        send_email: Whether to send email after creation (default True)

    Returns:
        Created invoice data from Xero or None if failed
    """
    try:
        # Step 1: Find or create contact (skip if contact_id provided)
        if not contact_id:
            logger.info(f"Looking up contact: {contact_name}")
            contact_id = await find_contact_by_name(contact_name, access_token, xero_tenant_id)

            if not contact_id:
                logger.info(f"Contact not found, creating new contact: {contact_name}")
                contact_id = await create_contact_for_invoice(
                    contact_name, access_token, xero_tenant_id
                )
        else:
            logger.info(f"Using provided contact_id: {contact_id}")

        if not contact_id:
            logger.error("Failed to find or create contact for invoice")
            return None

        # Step 2: Build invoice payload
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Xero-Tenant-Id": xero_tenant_id,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        # Convert line items to Xero format
        xero_line_items = []
        for item in line_items:
            xero_item = {
                "Description": item.get("description", ""),
                "Quantity": float(item.get("quantity", 1)),
                "UnitAmount": float(item.get("unit_price", 0)),
                "AccountCode": item.get("account_code", "200"),  # Default: Sales account
                "TaxType": map_vat_rate(item.get("vat_rate", "standard")),
            }
            xero_line_items.append(xero_item)

        invoice_payload = {
            "Invoices": [
                {
                    "Type": "ACCREC",  # Accounts Receivable (sales invoice)
                    "Status": "AUTHORISED",  # Ready to send
                    "Contact": {"ContactID": contact_id},
                    "DueDate": due_date,
                    "LineAmountTypes": "Exclusive",  # Amounts are exclusive of tax
                    "LineItems": xero_line_items,
                }
            ]
        }

        logger.info(f"Creating invoice in Xero for contact: {contact_name}")
        logger.debug(f"Invoice payload: {invoice_payload}")

        # Step 3: Create the invoice
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.xero.com/api.xro/2.0/Invoices",
                headers=headers,
                json=invoice_payload,
                timeout=30.0,
            )

            logger.info(f"Xero invoice creation response: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                invoices = data.get("Invoices", [])
                if invoices:
                    created_invoice = invoices[0]
                    invoice_id = created_invoice.get("InvoiceID")
                    invoice_number = created_invoice.get("InvoiceNumber")
                    total = created_invoice.get("Total", 0)

                    logger.info(
                        f"Successfully created invoice {invoice_number} (ID: {invoice_id}) "
                        f"for {contact_name}, total: {total}"
                    )

                    # Step 4: Get online invoice URL
                    online_url = await get_online_invoice_url(
                        invoice_id, access_token, xero_tenant_id
                    )

                    # Step 5: Send email if requested
                    email_sent = False
                    email_error = None
                    if send_email:
                        email_sent, email_error = await send_invoice_email(
                            invoice_id, access_token, xero_tenant_id
                        )

                    return {
                        "invoice_id": invoice_id,
                        "invoice_number": invoice_number,
                        "contact_name": contact_name,
                        "contact_id": contact_id,
                        "total": total,
                        "status": "AUTHORISED",
                        "online_invoice_url": online_url,
                        "email_sent": email_sent,
                        "email_error": email_error,
                    }
                else:
                    logger.error("No invoice returned in response")
                    return None

            elif response.status_code == 401:
                logger.error("Xero API authentication failed (401)")
                return None

            elif response.status_code == 400:
                error_detail = response.json() if "application/json" in response.headers.get(
                    "content-type", ""
                ) else response.text
                logger.error(f"Xero API bad request (400): {error_detail}")
                return None

            else:
                logger.error(f"Xero API error: {response.status_code} - {response.text}")
                return None

    except httpx.TimeoutException:
        logger.error("Xero API request timed out")
        return None
    except Exception as e:
        logger.error(f"Error creating invoice in Xero: {e}")
        return None


async def get_xero_contacts(
    access_token: str,
    xero_tenant_id: str,
) -> list[dict] | None:
    """
    Get list of customer contacts from Xero.

    Args:
        access_token: Xero OAuth2 access token
        xero_tenant_id: Xero tenant ID

    Returns:
        List of contact dicts with contact_id, name, email, or None if failed
    """
    try:
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Xero-Tenant-Id": xero_tenant_id,
            "Accept": "application/json",
        }

        # Get customers only, ordered by name
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://api.xero.com/api.xro/2.0/Contacts?where=IsCustomer==true&order=Name",
                headers=headers,
                timeout=30.0,
            )

            logger.info(f"Xero get contacts response: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                contacts = data.get("Contacts", [])

                # Transform to simplified format
                result = []
                for contact in contacts:
                    result.append({
                        "contact_id": contact.get("ContactID"),
                        "name": contact.get("Name"),
                        "email": contact.get("EmailAddress"),
                    })

                logger.info(f"Retrieved {len(result)} contacts from Xero")
                return result
            else:
                logger.error(f"Failed to get contacts: {response.status_code} - {response.text}")
                return None

    except Exception as e:
        logger.error(f"Error getting contacts from Xero: {e}")
        return None


async def get_online_invoice_url(
    invoice_id: str,
    access_token: str,
    xero_tenant_id: str,
) -> str | None:
    """
    Get the online invoice URL for sharing.

    Args:
        invoice_id: Xero Invoice ID
        access_token: Xero OAuth2 access token
        xero_tenant_id: Xero tenant ID

    Returns:
        Online invoice URL or None if failed
    """
    try:
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Xero-Tenant-Id": xero_tenant_id,
            "Accept": "application/json",
        }

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://api.xero.com/api.xro/2.0/Invoices/{invoice_id}/OnlineInvoice",
                headers=headers,
                timeout=30.0,
            )

            logger.info(f"Xero get online invoice URL response: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                online_invoices = data.get("OnlineInvoices", [])
                if online_invoices:
                    url = online_invoices[0].get("OnlineInvoiceUrl")
                    logger.info(f"Retrieved online invoice URL: {url}")
                    return url
                logger.warning("No online invoice URL in response")
                return None
            else:
                logger.error(f"Failed to get online invoice URL: {response.status_code}")
                return None

    except Exception as e:
        logger.error(f"Error getting online invoice URL: {e}")
        return None


async def send_invoice_email(
    invoice_id: str,
    access_token: str,
    xero_tenant_id: str,
) -> tuple[bool, str | None]:
    """
    Send invoice email via Xero.

    The email will be sent to the contact's primary email address.
    Invoice must be AUTHORISED or SUBMITTED status.

    Args:
        invoice_id: Xero Invoice ID
        access_token: Xero OAuth2 access token
        xero_tenant_id: Xero tenant ID

    Returns:
        Tuple of (success: bool, error_message: str | None)
    """
    try:
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Xero-Tenant-Id": xero_tenant_id,
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient() as client:
            # POST with empty body - Xero expects 204 No Content on success
            response = await client.post(
                f"https://api.xero.com/api.xro/2.0/Invoices/{invoice_id}/Email",
                headers=headers,
                content="",  # Empty body
                timeout=30.0,
            )

            logger.info(f"Xero send email response: {response.status_code}")

            if response.status_code == 204:
                logger.info(f"Successfully sent invoice email for {invoice_id}")
                return True, None
            elif response.status_code == 400:
                # Could be rate limit, invalid status, or no email on contact
                error_msg = "Failed to send email - check contact has email address"
                try:
                    error_data = response.json()
                    if "Message" in error_data:
                        error_msg = error_data["Message"]
                except Exception:
                    pass
                logger.warning(f"Email send failed (400): {error_msg}")
                return False, error_msg
            else:
                error_msg = f"Email send failed with status {response.status_code}"
                logger.error(error_msg)
                return False, error_msg

    except Exception as e:
        error_msg = f"Error sending invoice email: {e}"
        logger.error(error_msg)
        return False, error_msg


async def get_xero_tenant_id(access_token: str) -> str | None:
    """
    Get the Xero tenant ID for the authorized user.

    Args:
        access_token: Xero OAuth2 access token

    Returns:
        Xero tenant ID or None if failed
    """
    try:
        logger.info("Attempting to get Xero tenant ID")

        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://api.xero.com/connections",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                },
                timeout=30.0,
            )

            logger.info(f"Xero connections response status: {response.status_code}")

            if response.status_code == 401:
                logger.error("Xero token is invalid or expired (401 Unauthorized)")
                return None
            elif response.status_code == 200:
                connections = response.json()
                logger.info(f"Retrieved {len(connections)} Xero connections")

                if connections and len(connections) > 0:
                    tenant_id = connections[0].get("tenantId")
                    logger.info(f"Retrieved Xero tenant ID: {tenant_id}")
                    return tenant_id
                else:
                    logger.error("No Xero tenants found for this connection")
            else:
                logger.error(
                    f"Unexpected response from Xero: {response.status_code} - {response.text}"
                )

        return None

    except httpx.HTTPStatusError as e:
        logger.error(
            f"HTTP error getting Xero tenant ID: {e.response.status_code} - {e.response.text}"
        )
        return None
    except Exception as e:
        logger.error(f"Error getting Xero tenant ID: {e}")
        return None
