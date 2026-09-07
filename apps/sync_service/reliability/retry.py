from __future__ import annotations

from dataclasses import dataclass
import random
import time
from typing import Callable, TypeVar

from shared.errors.codes import ErrorCode
from shared.errors.exceptions import SyncError


T = TypeVar("T")


@dataclass(frozen=True)
class RetryConfig:
    max_attempts: int
    base_delay_ms: int
    max_delay_ms: int


def is_retryable(exc: Exception) -> bool:
    if not isinstance(exc, SyncError):
        return False
    return exc.code in {ErrorCode.CONNECTOR_TRANSIENT_ERROR, ErrorCode.RATE_LIMITED}


def with_retry(operation: Callable[[], T], config: RetryConfig) -> tuple[T, int]:
    """Run operation with exponential backoff and jitter, returning result and retry count."""
    if config.max_attempts < 1:
        raise ValueError("max_attempts must be >= 1")

    attempt = 1
    retries = 0
    while True:
        try:
            return operation(), retries
        except Exception as exc:
            if attempt >= config.max_attempts or not is_retryable(exc):
                raise

            base = min(config.max_delay_ms, config.base_delay_ms * (2 ** (attempt - 1)))
            jitter = random.randint(0, max(1, base // 5))
            time.sleep((base + jitter) / 1000.0)
            attempt += 1
            retries += 1
