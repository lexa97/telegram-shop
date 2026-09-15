# Память проекта (журнал работ)

Этот файл — **единый источник контекста** для команды и для AI-агентов: что делаем, что обсуждаем, что получилось.  
Обновляйте его по ходу работы (короткие записи с датой лучше длинных отчётов).

## Как вести журнал

- **Решения** — что выбрали и почему (1–3 предложения).
- **Обсуждения** — варианты и вопросы по ходу работы.
- **Отвергли** — идеи, от которых отказались, и кратко почему (чтобы не возвращаться без причины).
- **Результаты** — что смержено, как проверить, ссылки на PR/коммиты.
- **Граф кода (Graphify)** — пересборка **после merge в `main`**: `./devtools/graphify/refresh-after-merge.sh` (см. skill `/pr-memory-graphify`).

**Ритуал:** PR готов → запись в MEMORY в ветке PR; PR смержен → обновить `graphify-out/` на `main`.

**Справочник по коду для агентов:** [`AGENT_CODEBASE.md`](AGENT_CODEBASE.md) — модули, модели, транзакции, сценарии.

---

## 2026-09-15 — PR: подготовка Graphify + skill pr-memory-graphify

**Ветка:** `cursor/graphiti-memory-setup-3d1e` → `main`  
**PR:** https://github.com/lexa97/telegram-shop/pull/1

### Сделали

- Локальный **Graphify** (`graphify-out/`, `devtools/graphify/`).
- Журнал **MEMORY.md** и skill **`/pr-memory-graphify`**: память при готовности PR, Graphify после merge.
- Скрипт `devtools/graphify/refresh-after-merge.sh`.

### Обсуждали

- Graphiti (Neo4j/OpenAI) vs **Graphify** — нужен локальный граф без API.

### Отвергли

- *Graphiti + Neo4j + OpenAI* — *причина:* пользователю нужен локальный **graphify**, не Zep Graphiti.

### Проверка

- `graphify update .` и `graphify cluster-only . --no-label` на репозитории.
- Skill: `.cursor/skills/pr-memory-graphify/SKILL.md`.

### Graphify

- После merge PR #1: `git checkout main && git pull && ./devtools/graphify/refresh-after-merge.sh`, коммит `graphify-out/`.

---

## 2026-09-15 — Подготовка окружения

### Контекст

Репозиторий: **Telegram Shop Bot** — бот для продажи цифровых товаров (каталог, корзина, оплаты, админка в чате и веб).

### Что сделали

- Подключён **Graphify** (`graphifyy`): граф в `graphify-out/`, скрипт `devtools/graphify/build-graph.sh`, правила Cursor `graphify.mdc` + `project-memory.mdc`.
- Убрана ошибочная заготовка под Graphiti (Neo4j/OpenAI) — не нужна для нашего сценария.

### Стек (кратко)

| Слой | Технологии |
|------|------------|
| Бот | Python 3.11+, aiogram 3.22 |
| БД | PostgreSQL 16, SQLAlchemy 2.0 async, Alembic |
| Кэш / FSM | Redis 7 (опционально) |
| Админка | SQLAdmin, Starlette, uvicorn (`/admin`, `/health`, `/metrics`) |
| Контейнеры | Docker Compose (`db`, `redis`, `bot`) |

### Структура кода

```
run.py                 → точка входа, asyncio.run(start_bot)
bot/main.py            → жизненный цикл: Dispatcher, middleware, фоновые задачи, uvicorn
bot/handlers/          → user (магазин, корзина, оплаты) + admin (CRUD, рассылки)
bot/database/          → модели, CRUD, транзакции, аудит
bot/misc/services/     → платежи, recovery, cleanup, broadcast
bot/web/               → SQLAdmin + export
bot/middleware/        → rate limit, auth, security
bot/i18n/              → ru/en строки
migrations/            → Alembic
tests/                 → pytest (широкое покрытие handlers и DB)
```

### Архитектура (суть)

- **Один процесс, один event loop**: бот, веб-панель и воркеры — без отдельного брокера.
- Middleware (снаружи внутрь): RateLimit → Analytics → Auth → Security → роутеры.
- Redis выключен (`REDIS_ENABLED=0`) → in-memory FSM, без shared cache.

### Как запустить (основное приложение)

**Docker (рекомендуется):**

```bash
cp .env.example .env   # TOKEN, OWNER_ID, POSTGRES_*
docker compose up -d --build
# Админка: http://localhost:9090/admin
```

**Локально:**

```bash
python3.11 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
alembic upgrade head
python run.py
```

### Graphify (граф по коду, локально)

```bash
uv tool install graphifyy   # или pipx
graphify update .
graphify cluster-only . --no-label
graphify query "payment handlers" --graph graphify-out/graph.json
```

Подробнее: `devtools/graphify/README.md`. Интерактив: `graphify-out/graph.html`.

### Открытые вопросы

- [ ] Какие доработки продукта в приоритете после подготовки?
- [ ] Нужен ли MCP `python -m graphify.serve graphify-out/graph.json` в Cursor?

---

## Шаблон новой записи (PR ready)

```markdown
## YYYY-MM-DD — PR #N: Краткий заголовок

**Ветка:** `feature/...` → `main`  
**PR:** ссылка

### Сделали
- …

### Обсуждали
- …

### Отвергли
- *Идея:* … — *причина:* …

### Проверка
- …

### Graphify
- После merge: refresh на main (PR #N).
```
