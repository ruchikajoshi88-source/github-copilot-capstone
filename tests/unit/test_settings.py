import pytest

from shared.config.settings import load_settings_from_env
from shared.errors.exceptions import ConfigError


def test_load_settings_from_env_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SYNC_REPOSITORY_ID", "repo-123")
    monkeypatch.setenv("SYNC_SOURCE_ROOT", "docs")
    monkeypatch.setenv("SYNC_INCLUDE_PATTERNS", "**/*.md,notes/*.md")
    monkeypatch.setenv("SYNC_EXCLUDE_PATTERNS", "archive/*")
    monkeypatch.setenv("SYNC_RETRY_MAX_ATTEMPTS", "3")
    monkeypatch.setenv("SYNC_RETRY_BASE_DELAY_MS", "250")
    monkeypatch.setenv("SYNC_RETRY_MAX_DELAY_MS", "2000")

    settings = load_settings_from_env()

    assert settings.repository_id == "repo-123"
    assert settings.source_root == "docs"
    assert settings.include_patterns == ("**/*.md", "notes/*.md")
    assert settings.exclude_patterns == ("archive/*",)
    assert settings.retry_policy.max_attempts == 3


def test_load_settings_from_env_missing_required(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SYNC_REPOSITORY_ID", raising=False)
    monkeypatch.delenv("SYNC_SOURCE_ROOT", raising=False)

    with pytest.raises(ConfigError):
        load_settings_from_env()
