# Integration tests (mock Telegram)

Сценарии из [docs/testing/integration-scenarios.md](../../docs/testing/integration-scenarios.md).

## Fixtures

Общие фикстуры из [`tests/conftest.py`](../conftest.py): `user_factory`, `item_factory`, `make_message`, `make_callback_query`, `fsm_context`, `mock_bot`, …

## Маркер

Все тесты в этой папке помечены `@pytest.mark.integration` (см. `conftest.py`).

```bash
pytest tests/integration/              # только интеграция
pytest -m integration                  # то же по маркеру
pytest -m "not integration"            # без интеграции (если понадобится)
pytest                                 # полный suite, интеграция включена
```

## Именование файлов

`test_int_<номер>_<краткий_slug>.py`, например `test_int_001_start_profile.py`.

В docstring класса или функции:

```python
"""Scenario: INT-001 — /start и переход в профиль."""
```

## Шаблон теста

```python
import pytest
from aiogram.enums.chat_type import ChatType

from bot.handlers.user.main import start, profile_callback_handler


@pytest.mark.asyncio
class TestInt001StartProfile:
    """Scenario: INT-001 — /start и переход в профиль."""

    async def test_flow(self, make_message, make_callback_query, fsm_context):
        msg = make_message(text="/start", user_id=900001)
        msg.chat.type = ChatType.PRIVATE
        await start(msg, fsm_context)

        call = make_callback_query(data="profile", user_id=900001)
        await profile_callback_handler(call, fsm_context)

        call.message.edit_text.assert_called()
```

Удалите или закомментируйте пример выше, когда появятся реальные сценарии — или оставьте как эталон, скопировав в отдельный файл.
