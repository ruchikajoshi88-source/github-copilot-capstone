from __future__ import annotations

import pytest


@pytest.mark.integration
@pytest.mark.requires_env
def test_external_dependencies_reachable(require_external_dependencies: None) -> None:
    assert require_external_dependencies is None
