import pytest

from apps.sync_service.reliability.retry import RetryConfig, with_retry
from shared.errors.exceptions import RateLimitedError, ValidationError


def test_with_retry_succeeds_after_transient_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    attempts = {"count": 0}

    def no_sleep(_: float) -> None:
        return None

    monkeypatch.setattr("apps.sync_service.reliability.retry.time.sleep", no_sleep)

    def operation() -> str:
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise RateLimitedError("429")
        return "ok"

    result, retries = with_retry(operation, RetryConfig(max_attempts=5, base_delay_ms=1, max_delay_ms=2))

    assert result == "ok"
    assert retries == 2


def test_with_retry_does_not_retry_non_retryable() -> None:
    def operation() -> str:
        raise ValidationError("bad")

    with pytest.raises(ValidationError):
        with_retry(operation, RetryConfig(max_attempts=5, base_delay_ms=1, max_delay_ms=2))
