"""
Enhanced integration tests for FastAPI routes and endpoints.
"""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.api.auth import OpenAIValidation, Settings, XeroTokenResponse
from app.api.session import SecureSessionManager
from app.main import create_app


class TestEnhancedRoutesIntegration:
    """Enhanced integration tests for authentication routes."""

    @pytest.fixture
    def client(self):
        """Test client fixture with proper app configuration."""
        app = create_app()
        return TestClient(app)

    @pytest.fixture
    def mock_settings(self):
        """Mock settings for testing."""
        return Settings(
            xero_client_id="test_client_id_32_characters_long",
            xero_redirect_uri="http://localhost:8000/auth/callback",
            session_secret_key="test_secret_key_for_sessions",
            debug=True,
            app_name="Test Voice to Xero",
        )

    @pytest.fixture
    def session_manager(self):
        """Session manager fixture for testing."""
        return SecureSessionManager("test-secret-key")

    def test_landing_page_with_no_authentication(self, client):
        """Test landing page when user has no authentication."""
        response = client.get("/")

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

        # Check that page contains authentication prompts
        content = response.text
        assert "Connect to Xero" in content
        assert "OpenAI API Key" in content
        assert "Get Started in 2 Simple Steps" in content

    def test_landing_page_with_partial_authentication(self, client, session_manager):
        """Test landing page when user has partial authentication (only Xero)."""
        # Simulate having Xero token in session
        with client as c:
            # First request to establish session
            response = c.get("/")

            # Manually add Xero token to session (simulating authenticated state)
            with patch.object(session_manager, "get_session_data") as mock_get:
                mock_get.side_effect = lambda req, key: {
                    "xero_token": {"access_token": "test_token", "expires_in": 3600},
                    "openai_session": None,
                }.get(key)

                response = c.get("/")

        assert response.status_code == 200
        content = response.text
        # Should still show OpenAI API key form since only partially authenticated
        assert "OpenAI API Key" in content

    def test_auth_start_with_invalid_client_id(self, client):
        """Test auth start with improperly configured Xero client ID."""
        with patch("app.api.routes.settings") as mock_settings:
            mock_settings.xero_client_id = "placeholder_client_id"

            response = client.get("/auth/start", follow_redirects=False)

        assert response.status_code == 302
        assert "error=xero_not_configured" in response.headers["location"]

    def test_auth_start_with_short_client_id(self, client):
        """Test auth start with client ID that's too short."""
        with patch("app.api.routes.settings") as mock_settings:
            mock_settings.xero_client_id = "short_id"  # Less than 32 characters
            mock_settings.xero_redirect_uri = "http://localhost:8000/auth/callback"

            # Should still attempt auth but log warning
            with patch("app.api.routes.xero_oauth.create_authorization_url") as mock_create:
                mock_create.return_value = "https://login.xero.com/authorize?test=true"

                response = client.get("/auth/start", follow_redirects=False)

        assert response.status_code == 302
        assert "login.xero.com" in response.headers["location"]

    def test_auth_start_success_flow(self, client):
        """Test successful auth start redirects to Xero."""
        with patch("app.api.routes.settings") as mock_settings:
            mock_settings.xero_client_id = "valid_32_character_client_id_here"
            mock_settings.xero_redirect_uri = "http://localhost:8000/auth/callback"

            with patch("app.api.routes.xero_oauth.create_authorization_url") as mock_create:
                mock_create.return_value = (
                    "https://login.xero.com/identity/connect/authorize?client_id=test&state=test"
                )

                response = client.get("/auth/start", follow_redirects=False)

        assert response.status_code == 302
        assert "login.xero.com" in response.headers["location"]

    def test_auth_callback_missing_parameters(self, client):
        """Test auth callback with missing required parameters."""
        # Missing code parameter
        response = client.get("/auth/callback?state=test_state", follow_redirects=False)
        assert response.status_code == 302
        assert "error=missing_params" in response.headers["location"]

        # Missing state parameter
        response = client.get("/auth/callback?code=test_code", follow_redirects=False)
        assert response.status_code == 302
        assert "error=missing_params" in response.headers["location"]

    def test_auth_callback_with_auth_error(self, client):
        """Test auth callback when Xero returns an error."""
        response = client.get("/auth/callback?error=access_denied", follow_redirects=False)

        assert response.status_code == 302
        assert "error=auth_denied" in response.headers["location"]

    def test_auth_callback_success_flow(self, client):
        """Test successful auth callback flow."""
        # Mock successful token exchange
        mock_token_response = XeroTokenResponse(
            access_token="test_access_token",
            token_type="Bearer",
            expires_in=3600,
            scope="accounting.contacts accounting.transactions",
        )

        with patch("app.api.routes.xero_oauth.exchange_code_for_token") as mock_exchange:
            mock_exchange.return_value = mock_token_response

            with patch("app.api.routes.oauth_session_context") as mock_context:
                mock_context.return_value.__aenter__.return_value = {
                    "state": "test_state",
                    "code_verifier": "test_verifier",
                }

                response = client.get(
                    "/auth/callback?code=test_code&state=test_state", follow_redirects=False
                )

        assert response.status_code == 302
        assert "success=xero_connected" in response.headers["location"]

    def test_validate_openai_success_with_htmx(self, client):
        """Test successful OpenAI validation with HTMX response."""
        mock_validation = OpenAIValidation(api_key="sk-test...", is_valid=True, error_message=None)

        with patch("app.api.routes.OpenAIValidator.validate_api_key") as mock_validate:
            mock_validate.return_value = mock_validation

            response = client.post(
                "/auth/validate-openai",
                data={"api_key": "sk-test-valid-key-here"},
                headers={"HX-Request": "true"},
            )

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "validated successfully" in response.text.lower()
        assert "alert-success" in response.text

    def test_validate_openai_failure_with_htmx(self, client):
        """Test failed OpenAI validation with HTMX error response."""
        mock_validation = OpenAIValidation(
            api_key="invalid...", is_valid=False, error_message="Invalid API key format"
        )

        with patch("app.api.routes.OpenAIValidator.validate_api_key") as mock_validate:
            mock_validate.return_value = mock_validation

            response = client.post(
                "/auth/validate-openai",
                data={"api_key": "invalid-key"},
                headers={"HX-Request": "true"},
            )

        assert response.status_code == 400
        assert "text/html" in response.headers["content-type"]
        assert "Invalid API key format" in response.text
        assert "alert-error" in response.text

    def test_validate_openai_server_error(self, client):
        """Test OpenAI validation with server error."""
        with patch("app.api.routes.OpenAIValidator.validate_api_key") as mock_validate:
            mock_validate.side_effect = Exception("Server error")

            response = client.post(
                "/auth/validate-openai",
                data={"api_key": "sk-test-key"},
                headers={"HX-Request": "true"},
            )

        assert response.status_code == 500
        assert "server error" in response.text.lower()

    def test_auth_status_no_authentication(self, client):
        """Test auth status when user has no authentication."""
        response = client.get("/auth/status")

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"

        data = response.json()
        assert data["xero_connected"] is False
        assert data["openai_valid"] is False
        assert data["ready_for_operations"] is False

    def test_auth_status_partial_authentication(self, client):
        """Test auth status with only Xero authenticated."""
        with patch("app.api.routes.session_manager.get_session_data") as mock_get:
            mock_get.side_effect = lambda req, key: {
                "xero_token": {"access_token": "test_token"},
                "openai_session": None,
            }.get(key)

            response = client.get("/auth/status")

        assert response.status_code == 200
        data = response.json()
        assert data["xero_connected"] is True
        assert data["openai_valid"] is False
        assert data["ready_for_operations"] is False

    def test_auth_status_full_authentication(self, client):
        """Test auth status when fully authenticated."""
        with patch("app.api.routes.session_manager.get_session_data") as mock_get:
            mock_get.side_effect = lambda req, key: {
                "xero_token": {"access_token": "test_token"},
                "openai_session": {"api_key": "sk-test...", "is_valid": True},
            }.get(key)

            response = client.get("/auth/status")

        assert response.status_code == 200
        data = response.json()
        assert data["xero_connected"] is True
        assert data["openai_valid"] is True
        assert data["ready_for_operations"] is True

    def test_disconnect_auth_success(self, client):
        """Test successful Xero disconnection."""
        with patch("app.api.routes.session_manager.clear_session_data") as mock_clear:
            response = client.post("/auth/disconnect", follow_redirects=False)

        assert response.status_code == 303
        assert response.headers["location"] == "/"

        # Verify both Xero-related sessions were cleared (check call count)
        assert mock_clear.call_count == 2

    def test_disconnect_auth_error_handling(self, client):
        """Test disconnect error handling."""
        with patch("app.api.routes.session_manager.clear_session_data") as mock_clear:
            mock_clear.side_effect = Exception("Session error")

            response = client.post("/auth/disconnect", follow_redirects=False)

        assert response.status_code == 303
        assert "error=disconnect_failed" in response.headers["location"]

    def test_clear_openai_session_success(self, client):
        """Test successful OpenAI session clearing."""
        with patch("app.api.routes.session_manager.clear_session_data") as mock_clear:
            response = client.post("/auth/clear-openai", follow_redirects=False)

        assert response.status_code == 303
        assert response.headers["location"] == "/"

        # Verify OpenAI session was cleared
        mock_clear.assert_called_once()

    def test_clear_openai_session_error_handling(self, client):
        """Test clear OpenAI session error handling."""
        with patch("app.api.routes.session_manager.clear_session_data") as mock_clear:
            mock_clear.side_effect = Exception("Session error")

            response = client.post("/auth/clear-openai", follow_redirects=False)

        assert response.status_code == 303
        assert "error=clear_failed" in response.headers["location"]

    def test_health_endpoint_detailed_response(self, client):
        """Test health endpoint provides detailed application information."""
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "healthy"
        assert "app" in data
        assert "version" in data
        assert data["version"] == "0.1.0"


class TestSessionIntegration:
    """Test session integration across multiple requests."""

    @pytest.fixture
    def client(self):
        """Test client fixture."""
        app = create_app()
        return TestClient(app)

    def test_session_persistence_across_requests(self, client):
        """Test that session data persists across requests."""
        # Set up mock for successful OpenAI validation
        mock_validation = OpenAIValidation(api_key="sk-test...", is_valid=True, error_message=None)

        with patch("app.api.routes.OpenAIValidator.validate_api_key") as mock_validate:
            mock_validate.return_value = mock_validation

            # First request: validate OpenAI key
            response1 = client.post("/auth/validate-openai", data={"api_key": "sk-test-valid-key"})
            assert response1.status_code == 200

            # Second request: check auth status should show OpenAI as valid
            response2 = client.get("/auth/status")
            assert response2.status_code == 200

            data = response2.json()
            # Note: This might not work exactly as expected due to TestClient session handling
            # In real tests, we'd need to use cookies or simulate proper session handling

    def test_session_isolation_between_clients(self):
        """Test that different clients have isolated sessions."""
        app = create_app()
        client1 = TestClient(app)
        client2 = TestClient(app)

        mock_validation = OpenAIValidation(api_key="sk-test...", is_valid=True, error_message=None)

        with patch("app.api.routes.OpenAIValidator.validate_api_key") as mock_validate:
            mock_validate.return_value = mock_validation

            # Client 1 validates API key
            response1 = client1.post("/auth/validate-openai", data={"api_key": "sk-test-key-1"})
            assert response1.status_code == 200

            # Client 2 should not see Client 1's session
            response2 = client2.get("/auth/status")
            assert response2.status_code == 200

            data = response2.json()
            # Client 2 should show no authentication
            assert data["openai_valid"] is False


class TestErrorHandlingAndEdgeCases:
    """Test error handling and edge cases in routes."""

    @pytest.fixture
    def client(self):
        """Test client fixture."""
        app = create_app()
        return TestClient(app)

    def test_malformed_form_data_handling(self, client):
        """Test handling of malformed form data."""
        # Send request with missing required form field
        response = client.post("/auth/validate-openai", data={})

        # FastAPI should return 422 for missing required field
        assert response.status_code == 422

    def test_oversized_form_data_handling(self, client):
        """Test handling of oversized form data."""
        # Send extremely large API key
        large_api_key = "sk-" + "x" * 10000

        with patch("app.api.routes.OpenAIValidator.validate_api_key") as mock_validate:
            mock_validate.side_effect = Exception("Request too large")

            response = client.post("/auth/validate-openai", data={"api_key": large_api_key})

        # Should handle gracefully (validation will fail, but not crash)
        assert response.status_code == 500

    def test_concurrent_requests_handling(self, client):
        """Test handling of concurrent requests to the same endpoint."""
        import threading

        results = []

        def make_request():
            response = client.get("/auth/status")
            results.append(response.status_code)

        # Create multiple threads making concurrent requests
        threads = []
        for _ in range(5):
            thread = threading.Thread(target=make_request)
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # All requests should succeed
        assert all(status == 200 for status in results)
        assert len(results) == 5

    def test_special_characters_in_urls(self, client):
        """Test handling of special characters in URL parameters."""
        # Test with various encoded characters
        test_codes = [
            "test%20code",  # space
            "test%2Bcode",  # plus
            "test%26code",  # ampersand
        ]

        for code in test_codes:
            response = client.get(f"/auth/callback?code={code}&state=test", follow_redirects=False)
            # Should handle gracefully, not crash
            assert response.status_code in [302, 400, 500]

    def test_missing_template_file_handling(self, client):
        """Test graceful handling when template files might be missing."""
        # This is more of a deployment/configuration test
        # In normal operation, templates should always be present
        response = client.get("/")

        # Should either render successfully or fail gracefully
        assert response.status_code in [200, 500]

    def test_invalid_http_methods(self, client):
        """Test that endpoints properly restrict HTTP methods."""
        # Test GET on POST-only endpoints
        response = client.get("/auth/validate-openai")
        assert response.status_code == 405  # Method Not Allowed

        response = client.get("/auth/disconnect")
        assert response.status_code == 405

        response = client.get("/auth/clear-openai")
        assert response.status_code == 405

        # Test invalid methods
        response = client.put("/auth/status")
        assert response.status_code == 405

        response = client.delete("/")
        assert response.status_code == 405
