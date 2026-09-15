#!/usr/bin/env python3
"""Гибридный поиск по графу Graphiti (CLI)."""

from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv
from graphiti_core import Graphiti


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


async def search(query: str, limit: int) -> None:
    env_path = Path(__file__).with_name(".env")
    load_dotenv(env_path)

    uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
    user = os.environ.get("NEO4J_USER", "neo4j")
    password = os.environ.get("NEO4J_PASSWORD", "graphiti_dev_password")

    graphiti = Graphiti(uri, user, password)
    try:
        results = await graphiti.search(query, num_results=limit)
        if not results:
            print("(нет результатов)")
            return
        for i, edge in enumerate(results, 1):
            fact = getattr(edge, "fact", None) or str(edge)
            print(f"{i}. {fact}")
    finally:
        await graphiti.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("query", help="Вопрос по коду / архитектуре")
    parser.add_argument("-n", "--limit", type=int, default=8)
    args = parser.parse_args()
    asyncio.run(search(args.query, args.limit))


if __name__ == "__main__":
    main()
