#!/usr/bin/env bash
# Запускать на main после merge PR: пересборка graphify-out без LLM.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

BRANCH="$(git rev-parse --abbrev-ref HEAD)"
if [[ "$BRANCH" != "main" ]]; then
  echo "Предупреждение: вы на ветке '$BRANCH', ожидался main. Продолжаем пересборку графа." >&2
fi

exec "$ROOT/devtools/graphify/build-graph.sh"
