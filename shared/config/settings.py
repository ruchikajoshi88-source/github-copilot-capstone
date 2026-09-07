from __future__ import annotations

from dataclasses import dataclass
import os

from shared.errors.exceptions import ConfigError


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int
    base_delay_ms: int
    max_delay_ms: int


@dataclass(frozen=True)
class Settings:
    repository_id: str
    source_root: str
    include_patterns: tuple[str, ...]
    exclude_patterns: tuple[str, ...]
    retry_policy: RetryPolicy


REQUIRED_ENV_KEYS = ("SYNC_REPOSITORY_ID", "SYNC_SOURCE_ROOT")


def load_settings_from_env() -> Settings:
    missing = [key for key in REQUIRED_ENV_KEYS if not os.getenv(key)]
    if missing:
        raise ConfigError("Missing required environment variables", {"keys": ",".join(missing)})

    include_patterns = tuple(
        pattern.strip()
        for pattern in os.getenv("SYNC_INCLUDE_PATTERNS", "**/*.md").split(",")
        if pattern.strip()
    )
    exclude_patterns = tuple(
        pattern.strip()
        for pattern in os.getenv("SYNC_EXCLUDE_PATTERNS", "").split(",")
        if pattern.strip()
    )

    retry_policy = RetryPolicy(
        max_attempts=int(os.getenv("SYNC_RETRY_MAX_ATTEMPTS", "5")),
        base_delay_ms=int(os.getenv("SYNC_RETRY_BASE_DELAY_MS", "200")),
        max_delay_ms=int(os.getenv("SYNC_RETRY_MAX_DELAY_MS", "5000")),
    )

    if retry_policy.max_attempts < 1:
        raise ConfigError("SYNC_RETRY_MAX_ATTEMPTS must be >= 1")
    if retry_policy.base_delay_ms < 0 or retry_policy.max_delay_ms < retry_policy.base_delay_ms:
        raise ConfigError("Retry delay values are invalid")

    return Settings(
        repository_id=os.environ["SYNC_REPOSITORY_ID"],
        source_root=os.environ["SYNC_SOURCE_ROOT"],
        include_patterns=include_patterns,
        exclude_patterns=exclude_patterns,
        retry_policy=retry_policy,
    )
