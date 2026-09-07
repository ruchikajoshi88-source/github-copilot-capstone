from shared.errors.codes import ErrorCode
from shared.errors.exceptions import ConfigError, ValidationError


def test_config_error_code() -> None:
    err = ConfigError("missing key")
    assert err.code == ErrorCode.CONFIG_ERROR


def test_validation_error_string_representation() -> None:
    err = ValidationError("invalid frontmatter")
    assert "validation_error" in str(err)
