from enum import Enum


class ErrorCode(str, Enum):
    """Canonical error codes used across sync pipeline components."""

    VALIDATION_ERROR = "validation_error"
    SOURCE_ACCESS_ERROR = "source_access_error"
    CONNECTOR_TRANSIENT_ERROR = "connector_transient_error"
    RATE_LIMITED = "rate_limited"
    RETRY_EXHAUSTED = "retry_exhausted"
    EVENT_VALIDATION_ERROR = "event_validation_error"
    CONFIG_ERROR = "config_error"
    UNEXPECTED_ERROR = "unexpected_error"
