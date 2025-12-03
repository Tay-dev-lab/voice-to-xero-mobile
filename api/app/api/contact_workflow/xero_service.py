"""
Xero API service for creating contacts.
"""

import logging
from typing import Any

import httpx

from app.api.models import ContactCreate

logger = logging.getLogger(__name__)


async def create_xero_contact(
    contact_data: ContactCreate,
    access_token: str,
    xero_tenant_id: str,
) -> dict[str, Any] | None:
    """
    Create a contact in Xero using the API directly with httpx.

    Args:
        contact_data: Contact data to create
        access_token: Xero OAuth2 access token
        xero_tenant_id: Xero tenant ID

    Returns:
        Created contact data from Xero or None if failed
    """
    try:
        # Prepare headers
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Xero-Tenant-Id": xero_tenant_id,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        # Prepare contact data for Xero API
        contact_json = {
            "Name": contact_data.Name,
            "EmailAddress": contact_data.EmailAddress,
            "IsCustomer": True,
            "Addresses": [
                {
                    "AddressType": "STREET",
                    "AddressLine1": contact_data.Address.AddressLine1,
                    "City": contact_data.Address.City,
                    "PostalCode": contact_data.Address.PostalCode,
                    "Country": contact_data.Address.Country,
                }
            ],
        }

        # Wrap in Contacts array as required by Xero API
        request_body = {"Contacts": [contact_json]}

        logger.info(f"Creating contact in Xero: {contact_data.Name}")
        logger.debug(f"Request body: {request_body}")

        # Make API call to create contact
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.xero.com/api.xro/2.0/Contacts",
                headers=headers,
                json=request_body,
                timeout=30.0,
            )

            logger.info(f"Xero API response status: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                if data.get("Contacts") and len(data["Contacts"]) > 0:
                    created_contact = data["Contacts"][0]
                    logger.info(
                        f"Successfully created contact in Xero with ID: {created_contact.get('ContactID')}"
                    )
                    return {
                        "contact_id": created_contact.get("ContactID"),
                        "name": created_contact.get("Name"),
                        "email": created_contact.get("EmailAddress"),
                        "status": "success",
                    }
                else:
                    logger.error("No contact returned in response")
                    return None
            elif response.status_code == 401:
                logger.error("Xero API authentication failed (401)")
                return None
            elif response.status_code == 400:
                error_detail = (
                    response.json()
                    if response.headers.get("content-type", "").startswith("application/json")
                    else {}
                )
                logger.error(f"Xero API bad request (400): {error_detail}")
                return None
            else:
                logger.error(f"Xero API error: {response.status_code} - {response.text}")
                return None

    except httpx.TimeoutException:
        logger.error("Xero API request timed out")
        return None
    except Exception as e:
        logger.error(f"Error creating contact in Xero: {e}")
        return None


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

        # Call Xero connections endpoint to get tenant ID
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://api.xero.com/connections",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                },
            )

            logger.info(f"Xero connections response status: {response.status_code}")

            if response.status_code == 401:
                logger.error("Xero token is invalid or expired (401 Unauthorized)")
                return None
            elif response.status_code == 200:
                connections = response.json()
                logger.info(f"Retrieved {len(connections)} Xero connections")

                if connections and len(connections) > 0:
                    # Return the first tenant ID
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
