#!/usr/bin/env bash
# Локальная пересборка графа (без LLM). Запускать из корня репозитория.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

if ! command -v graphify >/dev/null 2>&1; then
  echo "graphify не найден. Установите: uv tool install graphifyy" >&2
  exit 1
fi

echo "==> graphify update (AST only)"
graphify update .

echo "==> graphify cluster-only (no LLM labels)"
graphify cluster-only . --no-label

echo "==> Done. Open graphify-out/graph.html or read graphify-out/GRAPH_REPORT.md"
