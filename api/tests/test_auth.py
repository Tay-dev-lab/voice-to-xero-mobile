"""
Tests for OAuth2 PKCE authentication and OpenAI validation functionality.
"""

import base64
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.auth import (
    OAuthSession,
    OpenAIValidation,
    OpenAIValidator,
    PKCEGenerator,
    Settings,
    XeroOAuth2,
    XeroTokenResponse,
)
from app.main import create_app


class TestPKCEGenerator:
    """Test PKCE code generation utilities."""

    def test_generate_pkce_pair(self):
        """Test PKCE code verifier and challenge generation."""
        verifier, challenge = PKCEGenerator.generate_pkce_pair()

        # Verify code verifier meets RFC 7636 requirements
        assert len(verifier) >= 43 and len(verifier) <= 128
        assert verifier != challenge  # Should be different (challenge is hash)

        # Verify verifier contains only allowed characters
        allowed_chars = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~")
        assert all(c in allowed_chars for c in verifier)

        # Verify challenge is base64url encoded

        try:
            # Should be decodable as base64url
            base64.urlsafe_b64decode(challenge + "==")  # Add padding if needed
        except Exception:
            pytest.fail("Code challenge is not valid base64url")

    def test_generate_pkce_pair_uniqueness(self):
        """Test that each call generates unique PKCE pairs."""
        pair1 = PKCEGenerator.generate_pkce_pair()
        pair2 = PKCEGenerator.generate_pkce_pair()

        # Should be different each time
        assert pair1[0] != pair2[0]  # Different verifiers
        assert pair1[1] != pair2[1]  # Different challenges


class TestXeroOAuth2:
    """Test Xero OAuth2 PKCE flow implementation."""

    @pytest.fixture
    def settings(self):
        """Test settings fixture."""
        return Settings(
            xero_client_id="test_client_id",
            xero_redirect_uri="http://localhost:8000/auth/callback",
            session_secret_key="test_secret_key",
            debug=True,
        )

    @pytest.fixture
    def xero_oauth(self, settings):
        """XeroOAuth2 instance fixture."""
        return XeroOAuth2(settings)

    def test_create_authorization_url(self, xero_oauth):
        """Test OAuth2 authorization URL creation."""
        session_data = {}
        url = xero_oauth.create_authorization_url(session_data)

        # Verify URL contains required components
        assert "login.xero.com" in url
        assert "code_challenge" in url
        assert "code_challenge_method=S256" in url
        assert "response_type=code" in url
        assert f"client_id={xero_oauth.settings.xero_client_id}" in url

        # Verify session data is stored
        assert "oauth_session" in session_data
        oauth_session = OAuthSession(**session_data["oauth_session"])
        assert oauth_session.state
        assert oauth_session.code_verifier
        assert oauth_session.code_challenge

    @pytest.mark.asyncio
    async def test_exchange_code_for_token_success(self, xero_oauth):
        """Test successful token exchange."""
        # Setup session data
        session_data = {}
        xero_oauth.create_authorization_url(session_data)
        oauth_session = OAuthSession(**session_data["oauth_session"])

        # Mock successful HTTP response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "test_access_token",
            "token_type": "Bearer",
            "expires_in": 3600,
            "scope": "accounting.contacts accounting.transactions",
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )

            result = await xero_oauth.exchange_code_for_token(
                code="test_code", state=oauth_session.state, session_data=session_data
            )

        assert isinstance(result, XeroTokenResponse)
        assert result.access_token == "test_access_token"
        assert result.token_type == "Bearer"

    @pytest.mark.asyncio
    async def test_exchange_code_for_token_invalid_state(self, xero_oauth):
        """Test token exchange with invalid state parameter."""
        session_data = {}
        xero_oauth.create_authorization_url(session_data)

        with pytest.raises(ValueError, match="Invalid state parameter"):
            await xero_oauth.exchange_code_for_token(
                code="test_code", state="invalid_state", session_data=session_data
            )

    @pytest.mark.asyncio
    async def test_exchange_code_for_token_no_session(self, xero_oauth):
        """Test token exchange with missing session data."""
        with pytest.raises(ValueError, match="No OAuth session data found"):
            await xero_oauth.exchange_code_for_token(
                code="test_code", state="test_state", session_data={}
            )

    @pytest.mark.asyncio
    async def test_exchange_code_for_token_http_error(self, xero_oauth):
        """Test token exchange with HTTP error."""
        session_data = {}
        xero_oauth.create_authorization_url(session_data)
        oauth_session = OAuthSession(**session_data["oauth_session"])

        # Mock HTTP 400 error response
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.headers = {"content-type": "application/json"}
        mock_response.json.return_value = {
            "error": "invalid_request",
            "error_description": "The request is invalid",
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )

            with pytest.raises(ValueError, match="Invalid request"):
                await xero_oauth.exchange_code_for_token(
                    code="invalid_code", state=oauth_session.state, session_data=session_data
                )


class TestOpenAIValidator:
    """Test OpenAI API key validation."""

    @pytest.mark.asyncio
    async def test_validate_api_key_success(self):
        """Test OpenAI API key validation with valid key."""
        with patch("app.api.auth.OpenAI") as mock_openai:
            # Mock successful API call
            mock_client = Mock()
            mock_client.models.list.return_value = []
            mock_openai.return_value = mock_client

            result = await OpenAIValidator.validate_api_key("sk-valid-key-here")

            assert result.is_valid is True
            assert result.api_key.startswith("sk-valid")  # Should be truncated
            assert result.api_key.endswith("...")  # Should end with ...
            assert result.error_message is None

    @pytest.mark.asyncio
    async def test_validate_api_key_invalid_key(self):
        """Test OpenAI API key validation with invalid key."""
        with patch("app.api.auth.OpenAI") as mock_openai:
            # Mock API key error
            mock_openai.side_effect = Exception("invalid api key")

            result = await OpenAIValidator.validate_api_key("invalid-key")

            assert result.is_valid is False
            assert "Invalid API key" in result.error_message

    @pytest.mark.asyncio
    async def test_validate_api_key_rate_limit(self):
        """Test OpenAI API key validation with rate limit error."""
        with patch("app.api.auth.OpenAI") as mock_openai:
            # Mock rate limit error
            mock_openai.side_effect = Exception("rate limit exceeded")

            result = await OpenAIValidator.validate_api_key("sk-test-key")

            assert result.is_valid is False
            assert "Rate limit exceeded" in result.error_message

    @pytest.mark.asyncio
    async def test_validate_api_key_quota_error(self):
        """Test OpenAI API key validation with quota error."""
        with patch("app.api.auth.OpenAI") as mock_openai:
            # Mock quota error
            mock_openai.side_effect = Exception("insufficient quota")

            result = await OpenAIValidator.validate_api_key("sk-test-key")

            assert result.is_valid is False
            assert "Insufficient OpenAI credits" in result.error_message

    @pytest.mark.asyncio
    async def test_validate_api_key_network_error(self):
        """Test OpenAI API key validation with network error."""
        with patch("app.api.auth.OpenAI") as mock_openai:
            # Mock network error
            mock_openai.side_effect = Exception("network error occurred")

            result = await OpenAIValidator.validate_api_key("sk-test-key")

            assert result.is_valid is False
            assert "Network error" in result.error_message


class TestModels:
    """Test Pydantic models."""

    def test_oauth_session_model(self):
        """Test OAuthSession model validation."""
        session = OAuthSession(
            state="test_state",
            code_verifier="test_verifier",
            code_challenge="test_challenge",
            redirect_uri="http://localhost:8000/callback",
        )

        assert session.state == "test_state"
        assert session.code_verifier == "test_verifier"
        assert session.created_at is not None

    def test_xero_token_response_model(self):
        """Test XeroTokenResponse model validation."""
        token = XeroTokenResponse(
            access_token="test_token", expires_in=3600, scope="accounting.contacts"
        )

        assert token.access_token == "test_token"
        assert token.token_type == "Bearer"  # Default value
        assert token.expires_in == 3600

    def test_openai_validation_model(self):
        """Test OpenAIValidation model validation."""
        validation = OpenAIValidation(api_key="sk-test...", is_valid=True)

        assert validation.api_key == "sk-test..."
        assert validation.is_valid is True
        assert validation.error_message is None


@pytest.fixture
def test_app():
    """Test FastAPI application fixture."""
    app = create_app()
    return app


@pytest.fixture
def client(test_app):
    """Test client fixture."""
    with TestClient(test_app) as client:
        yield client


class TestRoutes:
    """Test authentication routes."""

    def test_health_endpoint(self, client):
        """Test health check endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    def test_landing_page(self, client):
        """Test landing page loads."""
        response = client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_auth_status_endpoint(self, client):
        """Test authentication status endpoint."""
        response = client.get("/auth/status")
        assert response.status_code == 200
        data = response.json()

        assert "xero_connected" in data
        assert "openai_valid" in data
        assert "ready_for_operations" in data
        assert isinstance(data["xero_connected"], bool)
        assert isinstance(data["openai_valid"], bool)

    def test_validate_openai_endpoint_invalid_key(self, client):
        """Test OpenAI validation endpoint with invalid key."""
        with patch.object(OpenAIValidator, "validate_api_key") as mock_validate:
            mock_validate.return_value = OpenAIValidation(
                api_key="invalid...", is_valid=False, error_message="Invalid API key"
            )

            response = client.post("/auth/validate-openai", data={"api_key": "invalid-key"})

            assert response.status_code == 400
            # Response is HTML, not JSON for HTMX requests
            assert "Invalid API key" in response.text
            assert "alert-error" in response.text

    @patch.object(OpenAIValidator, "validate_api_key")
    def test_validate_openai_endpoint_valid_key(self, mock_validate, client):
        """Test OpenAI validation endpoint with valid key."""
        mock_validate.return_value = OpenAIValidation(api_key="sk-test...", is_valid=True)

        response = client.post("/auth/validate-openai", data={"api_key": "sk-valid-key-here"})

        assert response.status_code == 200
        # Response is HTML, not JSON for HTMX requests
        assert "validated successfully" in response.text.lower()
        assert "alert-success" in response.text

    def test_disconnect_auth_endpoint(self, client):
        """Test disconnect authentication endpoint."""
        response = client.post("/auth/disconnect", follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] == "/"

    def test_clear_openai_session_endpoint(self, client):
        """Test clear OpenAI session endpoint."""
        response = client.post("/auth/clear-openai", follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] == "/"
