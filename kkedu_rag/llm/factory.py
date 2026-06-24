"""Rebuildable LLM client + model factory, driven by runtime settings.

``client()`` returns the current AsyncOpenAI instance (pointed at the configured
host); ``rebuild()`` re-creates it after a settings change so edits apply live.
``chat_model()`` builds an SDK chat-model bound to the current client+model.
"""
from __future__ import annotations
from openai import AsyncOpenAI
from agents import OpenAIChatCompletionsModel
from ..runtime import startup  # noqa: F401  -- import for side-effects, before any client
from ..core import settings

_client: AsyncOpenAI | None = None


def rebuild() -> AsyncOpenAI:
    """(Re)create the shared client from current settings. Returns it."""
    global _client
    s = settings.get()
    _client = AsyncOpenAI(base_url=s["ollama_base_url"], api_key=s["api_key"] or "ollama")
    return _client


def client() -> AsyncOpenAI:
    """The current client singleton (built on first use)."""
    return _client or rebuild()


def chat_model() -> OpenAIChatCompletionsModel:
    """An SDK chat model bound to the current client and configured chat model."""
    return OpenAIChatCompletionsModel(model=settings.get()["chat_model"],
                                      openai_client=client())
