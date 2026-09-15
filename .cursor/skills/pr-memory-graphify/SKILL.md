---
name: pr-memory-graphify
description: Когда pull request готов к ревью — обновить docs/MEMORY.md (сделано, обсуждения, отвергнутые идеи). Когда PR смержен в main — пересобрать Graphify и закоммитить graphify-out. Вызывать при «PR готов», «перед ревью», «смержили», «после merge», или вручную /pr-memory-graphify.
---

# PR → память и Graphify

Два обязательных ритуала в этом репозитории. Не смешивайте их: **память — до/на готовности PR**, **Graphify — после merge в базовую ветку** (обычно `main`).

## Фаза A — Pull request готов (ещё не смержен)

**Триггеры:** PR открыт или помечен ready for review; агент завершил задачу и собирается создать/обновить PR; пользователь просит «зафиксировать в памяти».

### Шаги

1. Соберите факты из сессии и diff ветки:
   - номер/URL PR (если есть);
   - ветка → `main`;
   - список изменённых областей (модули, не каждый файл).
2. Откройте `docs/MEMORY.md` и **добавьте новую запись сверху** (после блока «Как вести журнал»), по шаблону ниже. Язык записи — **русский**, как в остальном MEMORY.
3. Обязательные блоки в записи:
   - **Сделали** — что реально вошло в PR (факты, не планы).
   - **Обсуждали** — варианты, вопросы, компромиссы.
   - **Отвергли** — идеи/подходы, от которых сознательно отказались, и **кратко почему** (чтобы не поднимать снова без причины).
   - **Проверка** — как убедиться, что работает (команды, URL, сценарий).
4. Закройте или обновите пункты в **Открытые вопросы** в MEMORY, если PR их решил или породил новые.
5. **Коммит в ту же ветку, что и PR:** только `docs/MEMORY.md` (и при необходимости правки шаблона — редко). Сообщение коммита в духе: `docs: memory for PR #N — краткое название`.
6. Запушьте ветку, чтобы ревьюер видел память вместе с кодом.

**Не делать в фазе A:** `graphify update` / полная пересборка графа — граф обновляем после merge (фаза B).

### Шаблон записи (PR ready)

```markdown
## YYYY-MM-DD — PR #N: Краткий заголовок

**Ветка:** `cursor/...` → `main`  
**PR:** https://github.com/.../pull/N

### Сделали

- …

### Обсуждали

- …

### Отвергли

- *Идея:* … — *причина:* …

### Проверка

- …

### Graphify

- После merge: `./devtools/graphify/refresh-after-merge.sh` (или вручную `graphify update .` + `cluster-only`).
```

---

## Фаза B — Pull request смержен

**Триггеры:** PR merged в `main`; пользователь пишет «смержили», «после merge», «обнови graphify».

### Шаги

1. Переключитесь на актуальный `main` и подтяните merge:
   ```bash
   git fetch origin main
   git checkout main
   git pull origin main
   ```
2. Убедитесь, что CLI установлен (`graphify` в PATH). Если нет:
   ```bash
   uv tool install graphifyy
   export PATH="$HOME/.local/bin:$PATH"
   ```
3. Пересоберите граф **локально, без LLM**:
   ```bash
   ./devtools/graphify/refresh-after-merge.sh
   ```
   Скрипт вызывает `build-graph.sh` (`graphify update .` + `graphify cluster-only . --no-label`).
4. Проверьте артефакты: `graphify-out/graph.json`, `GRAPH_REPORT.md`, `graphify-out/graph.html`.
5. В `docs/MEMORY.md` в записи этого PR добавьте одну строку под **Graphify** (или в **Результаты**): дата merge, хеш `main`, что граф обновлён.
6. Закоммитьте и запушьте в `main`:
   - `graphify-out/graph.json`
   - `graphify-out/GRAPH_REPORT.md`
   - `graphify-out/graph.html`
   - `graphify-out/manifest.json`
   - при изменении — `graphify-out/.graphify_analysis.json`
   - **не** коммитить `graphify-out/cache/` (в `.gitignore`).
7. Сообщение коммита: `chore(graphify): refresh graph after merge PR #N`.

### Если merge был без фазы A

Сначала выполните **фазу A** по памяти (ретроспективно по PR description и diff), затем фазу B.

---

## Быстрые команды

| Ситуация | Действие |
|----------|----------|
| PR готов | Редактировать `docs/MEMORY.md`, коммит в ветку PR |
| PR смержен | `git checkout main && git pull` → `./devtools/graphify/refresh-after-merge.sh` → коммит `graphify-out/` |

---

## Связанные файлы

- Журнал: `docs/MEMORY.md`
- Правило Cursor: `.cursor/rules/project-memory.mdc`
- Graphify: `devtools/graphify/README.md`, `.cursor/rules/graphify.mdc`
