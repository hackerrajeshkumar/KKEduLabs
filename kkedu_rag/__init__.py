"""kkedu_rag — an enterprise RAG CLI (OpenAI Agents SDK + Ollama gpt-oss).

Public entrypoint: ``main`` (async). Run as ``python -m kkedu_rag <docs...>``.
"""
from __future__ import annotations
from .cli import main

__all__ = ["main"]
