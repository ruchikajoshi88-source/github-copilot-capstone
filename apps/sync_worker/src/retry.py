from __future__ import annotations


class RetryPolicy:
    def __init__(self, max_attempts: int = 3) -> None:
        self.max_attempts = max_attempts

    def load_rules(self) -> dict[str, set[str]]:
        return {"retryable": {"timeout", "connection_error", "temporary"}}

    def should_retry(self, error_code: str | None, attempt: int) -> bool:
        if attempt < 0 or not error_code:
            return False

        rules = self.load_rules()
        retryable = rules.get("retryable", set())
        return attempt < self.max_attempts and str(error_code).lower() in retryable

    is_retryable = should_retry
    evaluate = should_retry
