#!/usr/bin/env python3
"""Индексирует структуру репозитория в Graphiti (эпизоды по модулям + обзор проекта)."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from graphiti_core import Graphiti
from graphiti_core.nodes import EpisodeType

SKIP_DIRS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    "htmlcov",
    "data",
    "logs",
    "assets",
    "neo4j_graphiti_data",
}
PY_ROOTS = ("bot", "migrations", "tests")
MAX_FILE_CHARS = 12_000
IMPORT_RE = re.compile(r"^(?:from|import)\s+[\w.]+", re.MULTILINE)


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def iter_python_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for sub in PY_ROOTS:
        base = root / sub
        if not base.is_dir():
            continue
        for path in base.rglob("*.py"):
            if any(part in SKIP_DIRS for part in path.parts):
                continue
            files.append(path)
    for name in ("run.py", "conftest.py"):
        p = root / name
        if p.is_file():
            files.append(p)
    return sorted(set(files))


def module_episode_body(root: Path, path: Path) -> str:
    rel = path.relative_to(root).as_posix()
    text = path.read_text(encoding="utf-8", errors="replace")
    if len(text) > MAX_FILE_CHARS:
        text = text[:MAX_FILE_CHARS] + "\n# ... truncated for indexing ...\n"
    imports = IMPORT_RE.findall(text)
    header = {
        "kind": "python_module",
        "path": rel,
        "imports_sample": imports[:40],
        "line_count": text.count("\n") + 1,
    }
    return json.dumps(
        {"meta": header, "source": text},
        ensure_ascii=False,
    )


def project_overview_body(root: Path, module_paths: list[str]) -> str:
    readme = (root / "README.md").read_text(encoding="utf-8", errors="replace")[:8000]
    overview = {
        "kind": "project_overview",
        "name": "Telegram Shop Bot",
        "entrypoint": "run.py → bot.main.start_bot",
        "stack": [
            "Python 3.11+",
            "aiogram 3",
            "PostgreSQL 16 + SQLAlchemy 2 async",
            "Redis 7 optional",
            "SQLAdmin + Starlette admin on :9090",
            "Docker Compose",
        ],
        "module_count": len(module_paths),
        "modules_sample": module_paths[:80],
        "readme_excerpt": readme,
    }
    return json.dumps(overview, ensure_ascii=False)


async def run_index(reset_note: str | None) -> None:
    env_path = Path(__file__).with_name(".env")
    load_dotenv(env_path)
    load_dotenv(repo_root() / ".env")

    uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
    user = os.environ.get("NEO4J_USER", "neo4j")
    password = os.environ.get("NEO4J_PASSWORD", "graphiti_dev_password")

    if not os.environ.get("OPENAI_API_KEY"):
        raise SystemExit(
            "OPENAI_API_KEY не задан. Скопируйте devtools/graphiti/.env.example → .env"
        )

    root = Path(os.environ.get("PROJECT_ROOT", repo_root())).resolve()
    py_files = iter_python_files(root)
    module_paths = [p.relative_to(root).as_posix() for p in py_files]
    now = datetime.now(timezone.utc)

    graphiti = Graphiti(uri, user, password)
    try:
        await graphiti.build_indices_and_constraints()

        await graphiti.add_episode(
            name="telegram-shop-project-overview",
            episode_body=project_overview_body(root, module_paths),
            source=EpisodeType.json,
            source_description="Repository overview for Telegram Shop Bot",
            reference_time=now,
        )

        if reset_note:
            await graphiti.add_episode(
                name=f"reindex-note-{int(now.timestamp())}",
                episode_body=reset_note,
                source=EpisodeType.text,
                source_description="Manual reindex note",
                reference_time=now,
            )

        for path in py_files:
            rel = path.relative_to(root).as_posix()
            await graphiti.add_episode(
                name=f"module:{rel}",
                episode_body=module_episode_body(root, path),
                source=EpisodeType.json,
                source_description=f"Python module {rel}",
                reference_time=now,
            )
            print(f"indexed {rel}")

        print(f"Done. Episodes: 1 overview + {len(py_files)} modules.")
    finally:
        await graphiti.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Index repo into Graphiti")
    parser.add_argument(
        "--note",
        help="Optional text episode appended before module ingest (e.g. sprint goal)",
    )
    args = parser.parse_args()
    asyncio.run(run_index(args.note))


if __name__ == "__main__":
    main()
