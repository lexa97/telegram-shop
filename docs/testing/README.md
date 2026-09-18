# Тестирование (документация)

| Документ | Назначение |
|----------|------------|
| [integration-scenarios.md](integration-scenarios.md) | Сценарии интеграционных (mock) потоков — черновик → код в `tests/integration/` |
| [../tz/14-tests-launch.md](../tz/14-tests-launch.md) | ТЗ по автотестам и запуску |
| [../../README.md#-testing](../../README.md#-testing) | Общий обзор pytest в репозитории |

## Два слоя автотестов

1. **`tests/test_*.py`** — модульные и handler-тесты (уже есть): быстрые, точечные проверки логики, FSM, CRUD.
2. **`tests/integration/`** — сценарии «как пользователь/админ в боте»: несколько шагов подряд, общая БД, мок Telegram (`make_message`, `make_callback_query`, `mock_bot` из `tests/conftest.py`).

Интеграционные тесты **не** ходят в реальный Telegram Bot API и **не** требуют Redis; поведение как в остальном suite.

## Рабочий процесс

1. Опишите сценарий в [integration-scenarios.md](integration-scenarios.md) (статус `draft` или `ready`).
2. Когда приложение готово к сценарию — статус `ready`, затем реализация в `tests/integration/test_<id>_<slug>.py`.
3. В docstring теста укажите `Scenario: INT-xxx` и обновите таблицу (статус `done`, ссылка на файл/функцию).
4. `pytest` — интеграционные тесты входят в общий прогон; только они: `pytest tests/integration/`.
