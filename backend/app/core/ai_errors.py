"""
ai_errors.py - Normalized AI Provider Error Taxonomy (Phase 23.1)

Standardizes all upstream foundational model error states into safe,
unambiguous categories without leaking upstream raw payloads, credentials,
or sensitive internal stack traces.
"""

from enum import Enum
from typing import Optional, Dict, Any

class AIErrorCode(str, Enum):
    AUTHENTICATION_ERROR = "AUTHENTICATION_ERROR"
    RATE_LIMIT_ERROR = "RATE_LIMIT_ERROR"
    MODEL_UNAVAILABLE = "MODEL_UNAVAILABLE"
    PROVIDER_TIMEOUT = "PROVIDER_TIMEOUT"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    INVALID_REQUEST = "INVALID_REQUEST"
    STREAM_INTERRUPTED = "STREAM_INTERRUPTED"
    MOCK_DISABLED_IN_PROD = "MOCK_DISABLED_IN_PROD"
    UNKNOWN_PROVIDER_ERROR = "UNKNOWN_PROVIDER_ERROR"

class AIProviderException(Exception):
    """
    Standard domain exception for Zynova AI Core Engine.
    Carries standardized error code, human-safe explanation, and sanitized telemetry.
    """
    def __init__(
        self,
        code: AIErrorCode,
        message: str,
        provider_id: str,
        model: Optional[str] = None,
        status_code: Optional[int] = None,
        retryable: bool = False
    ):
        super().__init__(message)
        self.code = code
        self.message = message
        self.provider_id = provider_id
        self.model = model
        self.status_code = status_code
        self.retryable = retryable

    def to_dict(self) -> Dict[str, Any]:
        return {
            "error_code": self.code.value,
            "message": self.message,
            "provider": self.provider_id,
            "model": self.model,
            "retryable": self.retryable,
        }
