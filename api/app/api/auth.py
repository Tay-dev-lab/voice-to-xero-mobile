"""
OAuth2 PKCE authentication models and utilities for Xero integration.
"""

import asyncio
import base64
import logging
import secrets
from datetime import UTC, datetime
from functools import partial
from urllib.parse import urlencode

import httpx
from authlib.oauth2.rfc7636 import create_s256_code_challenge
from openai import OpenAI
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """Application settings with environment variable validation."""

    xero_client_id: str
    xero_redirect_uri: str
    session_secret_key: str
    debug: bool = False
    app_name: str = "Voice to Xero"
    xero_authorization_url: str = "https://login.xero.com/identity/connect/authorize"
    xero_token_url: str = "https://identity.xero.com/connect/token"
    cors_origins: str = "http://localhost:3000,http://localhost:8000"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


class OAuthSession(BaseModel):
    """OAuth2 session data for PKCE flow."""

    state: str
    code_verifier: str
    code_challenge: str
    redirect_uri: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class XeroTokenResponse(BaseModel):
    """Xero OAuth2 token response model."""

    access_token: str
    token_type: str = "Bearer"
    expires_in: int
    refresh_token: str | None = None
    scope: str

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class OpenAIValidation(BaseModel):
    """OpenAI API key validation result model."""

    api_key: str
    is_valid: bool = False
    error_message: str | None = None

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class PKCEGenerator:
    """PKCE (Proof Key for Code Exchange) utilities following RFC 7636."""

    @staticmethod
    def generate_pkce_pair() -> tuple[str, str]:
        """
        Generate PKCE code verifier and challenge pair.

        Returns:
            Tuple containing (code_verifier, code_challenge)
        """
        # Generate cryptographically secure random code verifier
        # RFC 7636: Length 43-128 characters, base64url-encoded
        code_verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode().rstrip("=")

        # Generate S256 code challenge using Authlib
        code_challenge = create_s256_code_challenge(code_verifier)

        return code_verifier, code_challenge


class XeroOAuth2:
    """Xero OAuth2 PKCE flow implementation."""

    def __init__(self, settings: Settings):
        self.settings = settings

    def create_authorization_url(self, session_data: dict) -> str:
        """
        Create Xero OAuth2 authorization URL with PKCE parameters.

        Args:
            session_data: Dictionary to store session state

        Returns:
            Authorization URL string
        """
        # Generate secure random state parameter
        state = secrets.token_urlsafe(32)

        # Generate PKCE pair
        code_verifier, code_challenge = PKCEGenerator.generate_pkce_pair()

        # Xero OAuth2 parameters
        params = {
            "response_type": "code",
            "client_id": self.settings.xero_client_id,
            "redirect_uri": self.settings.xero_redirect_uri,
            "scope": "accounting.contacts accounting.transactions offline_access",
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }

        # Store PKCE data in session for callback verification
        oauth_session = OAuthSession(
            state=state,
            code_verifier=code_verifier,
            code_challenge=code_challenge,
            redirect_uri=self.settings.xero_redirect_uri,
        )

        session_data["oauth_session"] = oauth_session.model_dump()

        return f"{self.settings.xero_authorization_url}?{urlencode(params)}"

    async def exchange_code_for_token(
        self, code: str, state: str, session_data: dict
    ) -> XeroTokenResponse | None:
        """
        Exchange authorization code for access token using PKCE.

        Args:
            code: Authorization code from callback
            state: State parameter from callback
            session_data: Session data containing PKCE parameters

        Returns:
            XeroTokenResponse if successful, None otherwise
        """
        # Verify session data exists
        oauth_session_data = session_data.get("oauth_session")
        if not oauth_session_data:
            raise ValueError("No OAuth session data found")

        oauth_session = OAuthSession(**oauth_session_data)

        # Verify state parameter
        if state != oauth_session.state:
            raise ValueError("Invalid state parameter")

        # Prepare token exchange request
        token_data = {
            "grant_type": "authorization_code",
            "client_id": self.settings.xero_client_id,
            "code": code,
            "redirect_uri": oauth_session.redirect_uri,
            "code_verifier": oauth_session.code_verifier,
        }

        headers = {"Content-Type": "application/x-www-form-urlencoded"}

        # Exchange code for token
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(
                    self.settings.xero_token_url, data=token_data, headers=headers
                )

                if response.status_code == 200:
                    token_data = response.json()
                    return XeroTokenResponse(**token_data)
                elif response.status_code == 400:
                    error_detail = (
                        response.json()
                        if response.headers.get("content-type", "").startswith("application/json")
                        else {}
                    )
                    error_description = error_detail.get(
                        "error_description", "Bad request during token exchange"
                    )
                    raise ValueError(f"Invalid request: {error_description}")
                elif response.status_code == 401:
                    raise ValueError(
                        "Unauthorized: Invalid client credentials or authorization code"
                    )
                elif response.status_code >= 500:
                    raise Exception("Xero server error. Please try again later.")
                else:
                    raise Exception(f"Token exchange failed with status {response.status_code}")

            except httpx.TimeoutException:
                raise Exception("Request to Xero timed out. Please try again.")
            except httpx.NetworkError as e:
                raise Exception(f"Network error connecting to Xero: {str(e)}")
            except httpx.HTTPError as e:
                raise Exception(f"HTTP error during token exchange: {str(e)}")

    async def refresh_token(self, refresh_token: str) -> XeroTokenResponse | None:
        """
        Refresh an expired Xero access token using refresh token.

        Args:
            refresh_token: The refresh token from previous authentication

        Returns:
            XeroTokenResponse if successful, None otherwise
        """
        # Prepare token refresh request
        token_data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": self.settings.xero_client_id,
        }

        headers = {"Content-Type": "application/x-www-form-urlencoded"}

        # Request new access token
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(
                    self.settings.xero_token_url, data=token_data, headers=headers
                )

                if response.status_code == 200:
                    token_data = response.json()
                    return XeroTokenResponse(**token_data)
                elif response.status_code == 400:
                    # Refresh token might be invalid or expired
                    error_detail = (
                        response.json()
                        if response.headers.get("content-type", "").startswith("application/json")
                        else {}
                    )
                    error_description = error_detail.get(
                        "error_description", "Failed to refresh token"
                    )
                    logger.error(f"Token refresh failed: {error_description}")
                    return None
                elif response.status_code == 401:
                    logger.error("Token refresh failed: Invalid refresh token")
                    return None
                else:
                    logger.error(f"Token refresh failed with status {response.status_code}")
                    return None

            except Exception as e:
                logger.error(f"Error refreshing token: {str(e)}")
                return None


class OpenAIValidator:
    """OpenAI API key validation utilities."""

    @staticmethod
    async def validate_api_key(api_key: str) -> OpenAIValidation:
        """
        Validate OpenAI API key with minimal API call.

        Args:
            api_key: OpenAI API key to validate

        Returns:
            OpenAIValidation result with validity status
        """
        try:
            # Initialize OpenAI client following existing pattern
            client = OpenAI(api_key=api_key)

            # Make minimal API call to test key validity in executor
            # Use models.list() as it's lightweight and quick
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, partial(client.models.list))

            # Don't expose the full API key in return
            safe_key = f"{api_key[:8]}..." if len(api_key) > 8 else "***"
            return OpenAIValidation(api_key=safe_key, is_valid=True)

        except Exception as e:
            error_msg = str(e)
            # Don't expose the full API key in error messages
            safe_key = f"{api_key[:8]}..." if len(api_key) > 8 else "***"

            # Provide user-friendly error messages for common issues
            if "invalid api key" in error_msg.lower():
                error_msg = "Invalid API key. Please check your key and try again."
            elif "rate limit" in error_msg.lower():
                error_msg = "Rate limit exceeded. Please try again in a moment."
            elif "insufficient quota" in error_msg.lower():
                error_msg = "Insufficient OpenAI credits. Please check your billing."
            elif "network" in error_msg.lower() or "connection" in error_msg.lower():
                error_msg = "Network error. Please check your connection and try again."
            else:
                # Generic error for unknown issues
                error_msg = "Unable to validate API key. Please try again."

            return OpenAIValidation(api_key=safe_key, is_valid=False, error_message=error_msg)
