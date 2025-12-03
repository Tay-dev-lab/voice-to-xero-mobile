"""
Tests for secure session management utilities.
"""

from datetime import UTC, datetime
from unittest.mock import Mock, patch

import pytest
from itsdangerous import BadSignature, SignatureExpired
from starlette.middleware.sessions import SessionMiddleware
from starlette.requests import Request

from app.api.session import (
    DateTimeAwareJSONEncoder,
    SecureSessionManager,
    get_session_middleware,
    oauth_session_context,
    openai_session_context,
    parse_datetime_in_dict,
)


class TestDateTimeAwareJSONEncoder:
    """Test custom JSON encoder for datetime objects."""

    def test_encode_datetime(self):
        """Test datetime encoding to ISO format."""
        encoder = DateTimeAwareJSONEncoder()
        test_datetime = datetime(2024, 1, 15, 10, 30, 45, tzinfo=UTC)

        result = encoder.default(test_datetime)
        assert result == "2024-01-15T10:30:45+00:00"

    def test_encode_non_datetime(self):
        """Test that non-datetime objects fall back to default behavior."""
        encoder = DateTimeAwareJSONEncoder()

        with pytest.raises(TypeError):
            encoder.default({"test": "object"})


class TestParseDatetimeInDict:
    """Test datetime parsing utility function."""

    def test_parse_created_at_field(self):
        """Test parsing of created_at datetime string."""
        data = {"created_at": "2024-01-15T10:30:45+00:00", "other_field": "test_value"}

        result = parse_datetime_in_dict(data)

        assert isinstance(result["created_at"], datetime)
        assert result["created_at"] == datetime(2024, 1, 15, 10, 30, 45, tzinfo=UTC)
        assert result["other_field"] == "test_value"

    def test_parse_nested_dict(self):
        """Test parsing datetime strings in nested dictionaries."""
        data = {
            "session": {"created_at": "2024-01-15T10:30:45+00:00", "state": "test_state"},
            "regular_field": "value",
        }

        result = parse_datetime_in_dict(data)

        assert isinstance(result["session"]["created_at"], datetime)
        assert result["session"]["state"] == "test_state"
        assert result["regular_field"] == "value"

    def test_parse_invalid_datetime(self):
        """Test handling of invalid datetime strings."""
        data = {"created_at": "invalid-datetime"}

        result = parse_datetime_in_dict(data)

        assert result["created_at"] == "invalid-datetime"

    def test_parse_list_with_dicts(self):
        """Test parsing datetime strings in lists containing dictionaries."""
        data = [{"created_at": "2024-01-15T10:30:45+00:00"}, {"other_field": "value"}]

        result = parse_datetime_in_dict(data)

        assert isinstance(result[0]["created_at"], datetime)
        assert result[1]["other_field"] == "value"

    def test_parse_primitive_values(self):
        """Test that primitive values are returned unchanged."""
        assert parse_datetime_in_dict("string") == "string"
        assert parse_datetime_in_dict(42) == 42
        assert parse_datetime_in_dict(None) is None


class TestSecureSessionManager:
    """Test secure session management functionality."""

    @pytest.fixture
    def session_manager(self):
        """Provide SecureSessionManager instance for testing."""
        return SecureSessionManager("test-secret-key", max_age=3600)

    @pytest.fixture
    def mock_request(self):
        """Provide mock request with session."""
        request = Mock(spec=Request)
        request.session = {}
        return request

    def test_init(self):
        """Test SecureSessionManager initialization."""
        manager = SecureSessionManager("secret", max_age=1800)

        assert manager.max_age == 1800
        assert manager.serializer.secret_key == b"secret"

    def test_set_and_get_session_data(self, session_manager, mock_request):
        """Test storing and retrieving session data."""
        test_data = {"key": "value", "number": 42}

        session_manager.set_session_data(mock_request, "test_key", test_data)
        result = session_manager.get_session_data(mock_request, "test_key")

        assert result == test_data

    def test_get_nonexistent_session_data(self, session_manager, mock_request):
        """Test retrieving non-existent session data returns None."""
        result = session_manager.get_session_data(mock_request, "nonexistent")

        assert result is None

    def test_datetime_serialization(self, session_manager, mock_request):
        """Test datetime objects are properly serialized and deserialized."""
        test_datetime = datetime(2024, 1, 15, 10, 30, 45, tzinfo=UTC)
        test_data = {"created_at": test_datetime, "value": "test"}

        session_manager.set_session_data(mock_request, "datetime_test", test_data)
        result = session_manager.get_session_data(mock_request, "datetime_test")

        assert isinstance(result["created_at"], datetime)
        assert result["created_at"] == test_datetime
        assert result["value"] == "test"

    def test_clear_session_data(self, session_manager, mock_request):
        """Test clearing specific session data."""
        test_data = {"key": "value"}

        session_manager.set_session_data(mock_request, "test_key", test_data)
        session_manager.clear_session_data(mock_request, "test_key")

        result = session_manager.get_session_data(mock_request, "test_key")
        assert result is None

    def test_clear_all_session_data(self, session_manager, mock_request):
        """Test clearing all session data."""
        session_manager.set_session_data(mock_request, "key1", {"data": "value1"})
        session_manager.set_session_data(mock_request, "key2", {"data": "value2"})

        session_manager.clear_all_session_data(mock_request)

        # Should clear the session dict
        assert len(mock_request.session) == 0 or mock_request.session == {}

    def test_invalid_signature_handling(self, session_manager, mock_request):
        """Test handling of tampered session data."""
        mock_request.session["test_key"] = "invalid.signature.data"

        with patch.object(
            session_manager.serializer, "loads", side_effect=BadSignature("Bad signature")
        ):
            result = session_manager.get_session_data(mock_request, "test_key")

        assert result is None
        assert "test_key" not in mock_request.session

    def test_expired_signature_handling(self, session_manager, mock_request):
        """Test handling of expired session data."""
        mock_request.session["test_key"] = "expired.signature.data"

        with patch.object(
            session_manager.serializer, "loads", side_effect=SignatureExpired("Signature expired")
        ):
            result = session_manager.get_session_data(mock_request, "test_key")

        assert result is None
        assert "test_key" not in mock_request.session

    def test_serialization_error_handling(self, session_manager, mock_request):
        """Test handling of serialization errors."""

        # Create data that can't be serialized
        class UnserializableClass:
            pass

        with pytest.raises(Exception):
            session_manager.set_session_data(mock_request, "test_key", UnserializableClass())


class TestOAuthSessionContext:
    """Test OAuth session context manager."""

    @pytest.fixture
    def session_manager(self):
        """Provide SecureSessionManager instance for testing."""
        return SecureSessionManager("test-secret-key")

    @pytest.fixture
    def mock_request(self):
        """Provide mock request with session."""
        request = Mock(spec=Request)
        request.session = {}
        return request

    @pytest.mark.asyncio
    async def test_oauth_context_new_session(self, session_manager, mock_request):
        """Test OAuth context manager with new session."""
        async with oauth_session_context(mock_request, session_manager) as oauth_data:
            assert oauth_data == {}
            oauth_data["state"] = "test_state"
            oauth_data["code_verifier"] = "test_verifier"

        # Verify data was saved
        result = session_manager.get_session_data(mock_request, "oauth_session")
        assert result["state"] == "test_state"
        assert result["code_verifier"] == "test_verifier"

    @pytest.mark.asyncio
    async def test_oauth_context_existing_session(self, session_manager, mock_request):
        """Test OAuth context manager with existing session data."""
        existing_data = {"state": "existing_state", "code_verifier": "existing_verifier"}
        session_manager.set_session_data(mock_request, "oauth_session", existing_data)

        async with oauth_session_context(mock_request, session_manager) as oauth_data:
            assert oauth_data["state"] == "existing_state"
            oauth_data["new_field"] = "new_value"

        # Verify updated data was saved
        result = session_manager.get_session_data(mock_request, "oauth_session")
        assert result["state"] == "existing_state"
        assert result["new_field"] == "new_value"

    @pytest.mark.asyncio
    async def test_oauth_context_clear_empty(self, session_manager, mock_request):
        """Test OAuth context manager clears session when empty."""
        existing_data = {"state": "existing_state"}
        session_manager.set_session_data(mock_request, "oauth_session", existing_data)

        async with oauth_session_context(mock_request, session_manager) as oauth_data:
            oauth_data.clear()  # Empty the dict

        # Verify session was cleared
        result = session_manager.get_session_data(mock_request, "oauth_session")
        assert result is None


class TestOpenAISessionContext:
    """Test OpenAI session context manager."""

    @pytest.fixture
    def session_manager(self):
        """Provide SecureSessionManager instance for testing."""
        return SecureSessionManager("test-secret-key")

    @pytest.fixture
    def mock_request(self):
        """Provide mock request with session."""
        request = Mock(spec=Request)
        request.session = {}
        return request

    @pytest.mark.asyncio
    async def test_openai_context_new_session(self, session_manager, mock_request):
        """Test OpenAI context manager with new session."""
        async with openai_session_context(mock_request, session_manager) as openai_data:
            assert openai_data == {}
            openai_data["api_key"] = "sk-test..."
            openai_data["is_valid"] = True

        # Verify data was saved
        result = session_manager.get_session_data(mock_request, "openai_session")
        assert result["api_key"] == "sk-test..."
        assert result["is_valid"] is True

    @pytest.mark.asyncio
    async def test_openai_context_existing_session(self, session_manager, mock_request):
        """Test OpenAI context manager with existing session data."""
        existing_data = {"api_key": "sk-existing...", "is_valid": True}
        session_manager.set_session_data(mock_request, "openai_session", existing_data)

        async with openai_session_context(mock_request, session_manager) as openai_data:
            assert openai_data["api_key"] == "sk-existing..."
            openai_data["last_validated"] = datetime.now(UTC)

        # Verify updated data was saved
        result = session_manager.get_session_data(mock_request, "openai_session")
        assert result["api_key"] == "sk-existing..."
        assert "last_validated" in result

    @pytest.mark.asyncio
    async def test_openai_context_clear_empty(self, session_manager, mock_request):
        """Test OpenAI context manager clears session when empty."""
        existing_data = {"api_key": "sk-test...", "is_valid": True}
        session_manager.set_session_data(mock_request, "openai_session", existing_data)

        async with openai_session_context(mock_request, session_manager) as openai_data:
            openai_data.clear()  # Empty the dict

        # Verify session was cleared
        result = session_manager.get_session_data(mock_request, "openai_session")
        assert result is None


class TestGetSessionMiddleware:
    """Test session middleware factory function."""

    def test_create_session_middleware(self):
        """Test session middleware creation with default settings."""
        # Test the function exists and returns a SessionMiddleware class
        result = get_session_middleware("test-secret-key")

        # Should return the SessionMiddleware class, not instance
        assert result == SessionMiddleware

    def test_middleware_configuration(self):
        """Test that middleware is configured for development environment."""
        result = get_session_middleware("production-secret")

        # Should return SessionMiddleware class
        assert result == SessionMiddleware
