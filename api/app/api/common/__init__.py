"""
Common utilities shared across the application.
"""

from app.api.common.response_negotiator import (
    ClientType,
    dual_response,
    get_client_type,
    json_error,
    json_success,
    wants_json,
)
from app.api.common.schemas import (
    APIResponse,
    AuthStatusData,
    ContactSubmitData,
    ContactSummaryData,
    ErrorCodes,
    ErrorDetail,
    FieldUpdateData,
    InvoiceSubmitData,
    InvoiceSummaryData,
    LineItemConfirmData,
    LineItemData,
    MobileTokenData,
    OpenAIValidationData,
    StepConfirmData,
    StepProcessData,
    WorkflowInitData,
)
from app.api.common.token_auth import (
    MobileAuthManager,
    MobileSession,
    TokenPayload,
    extract_bearer_token,
    get_openai_api_key,
    get_xero_token,
    require_mobile_auth,
)
from app.api.common.utils import get_session_or_ip

__all__ = [
    # Response negotiation
    "ClientType",
    "dual_response",
    "get_client_type",
    "json_error",
    "json_success",
    "wants_json",
    # Schemas
    "APIResponse",
    "AuthStatusData",
    "ContactSubmitData",
    "ContactSummaryData",
    "ErrorCodes",
    "ErrorDetail",
    "FieldUpdateData",
    "InvoiceSubmitData",
    "InvoiceSummaryData",
    "LineItemConfirmData",
    "LineItemData",
    "MobileTokenData",
    "OpenAIValidationData",
    "StepConfirmData",
    "StepProcessData",
    "WorkflowInitData",
    # Token auth
    "MobileAuthManager",
    "MobileSession",
    "TokenPayload",
    "extract_bearer_token",
    "get_openai_api_key",
    "get_xero_token",
    "require_mobile_auth",
    # Utils
    "get_session_or_ip",
]
