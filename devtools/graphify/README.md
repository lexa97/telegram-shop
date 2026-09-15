# Graphify — локальный граф кодовой базы

[Graphify](https://github.com/Graphify-Labs/graphify) (PyPI: **`graphifyy`**, CLI: `graphify`) строит граф проекта **на машине**: tree-sitter AST, без OpenAI/Neo4j. Для одного репозитория с кодом достаточно `graphify update` и `graphify cluster-only`.

## Установка CLI

```bash
# предпочтительно (изолированное окружение)
uv tool install graphifyy
# или: pipx install graphifyy

# убедитесь, что ~/.local/bin в PATH
export PATH="$HOME/.local/bin:$PATH"
```

## Построить / обновить граф (только код, без API)

Из **корня репозитория**:

```bash
./devtools/graphify/build-graph.sh
```

Или вручную:

```bash
graphify update .              # пересборка AST по .py и др.
graphify cluster-only . --no-label   # сообщества + GRAPH_REPORT.md + graph.html
```

Артефакты: `graphify-out/graph.json`, `GRAPH_REPORT.md`, `graph.html`.

## Запросы к графу

```bash
graphify query "cart checkout flow" --graph graphify-out/graph.json
graphify path "start_bot" "PaymentService"
graphify explain "SecurityMiddleware"
graphify god-nodes --top 15
```

## Cursor

Уже установлено правило: `.cursor/rules/graphify.mdc` (`graphify cursor install`).

После правок в коде: `graphify update .` (быстро, без LLM).

## MCP (опционально)

```bash
python -m graphify.serve graphify-out/graph.json
```

## Отличие от MEMORY

| | Graphify | `docs/MEMORY.md` |
|---|----------|------------------|
| Назначение | структура кода, зависимости | решения, обсуждения, наши доработки |
| Обновление | после изменений кода | после задач / созвонов |
