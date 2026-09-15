# Graphiti — граф знаний по репозиторию

[Graphiti](https://github.com/getzep/graphiti) строит **временной граф знаний** из текстовых «эпизодов».  
Здесь мы складываем обзор проекта и Python-модули (`bot/`, `tests/`, `migrations/`), чтобы искать связи семантически, а не только по grep.

Это **отдельно** от PostgreSQL/Redis бота.

## Требования

- Python 3.11+
- Docker (Neo4j)
- `OPENAI_API_KEY` (дефолтный LLM Graphiti) или настройка другого провайдера по [документации Graphiti](https://help.getzep.com/graphiti)

## Быстрый старт

```bash
# 1) Neo4j
docker compose -f devtools/graphiti/docker-compose.graphiti.yml up -d

# 2) venv только для graphiti
python3.11 -m venv devtools/graphiti/.venv
source devtools/graphiti/.venv/bin/activate
pip install -r devtools/graphiti/requirements-graphiti.txt

# 3) секреты
cp devtools/graphiti/.env.example devtools/graphiti/.env
# отредактируйте OPENAI_API_KEY

# 4) индексация (может занять несколько минут — LLM на каждый модуль)
python devtools/graphiti/index_project.py

# 5) поиск
python devtools/graphiti/search_graph.py "как устроена корзина и checkout"
```

Neo4j Browser: http://localhost:7474 (логин из `NEO4J_USER` / `NEO4J_PASSWORD`).

## Повторная индексация

Graphiti обновляет граф при новых эпизодах; для крупного рефакторинга можно:

- добавить заметку: `python devtools/graphiti/index_project.py --note "Sprint X: новая оплата"`
- или очистить volume Neo4j и проиндексировать заново:

```bash
docker compose -f devtools/graphiti/docker-compose.graphiti.yml down -v
docker compose -f devtools/graphiti/docker-compose.graphiti.yml up -d
python devtools/graphiti/index_project.py
```

## Cursor / MCP (опционально)

У Graphiti есть [MCP-сервер](https://github.com/getzep/graphiti/tree/main/mcp_server) для ассистентов.  
Его можно подключить в настройках MCP Cursor, указав тот же Neo4j и API-ключ. CLI в этом каталоге достаточен для локальной работы без MCP.

## Связь с MEMORY.md

`docs/MEMORY.md` — **журнал решений команды**. Graphiti — **машинный граф по коду**. После индексации имеет смысл в MEMORY фиксировать только бизнес-контекст и планы, не дублируя весь код.
