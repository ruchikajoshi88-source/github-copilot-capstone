from dataclasses import dataclass

from shared.errors.codes import ErrorCode


@dataclass
class SyncError(Exception):
    """Base sync exception with standardized classification."""

    code: ErrorCode
    message: str
    context: dict[str, str] | None = None

    def __str__(self) -> str:
        return f"{self.code.value}: {self.message}"


class ConfigError(SyncError):
    def __init__(self, message: str, context: dict[str, str] | None = None) -> None:
        super().__init__(ErrorCode.CONFIG_ERROR, message, context)


class ValidationError(SyncError):
    def __init__(self, message: str, context: dict[str, str] | None = None) -> None:
        super().__init__(ErrorCode.VALIDATION_ERROR, message, context)


class SourceAccessError(SyncError):
    def __init__(self, message: str, context: dict[str, str] | None = None) -> None:
        super().__init__(ErrorCode.SOURCE_ACCESS_ERROR, message, context)
