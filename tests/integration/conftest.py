"""Integration flow tests: multi-step bot scenarios with mock Telegram + real test DB."""

import pytest

# Все тесты в этой директории — интеграционные (см. docs/testing/integration-scenarios.md).
pytestmark = pytest.mark.integration
