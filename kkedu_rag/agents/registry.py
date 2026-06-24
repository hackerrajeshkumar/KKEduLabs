"""Live registry of the answerer + verifier agents, rebuildable at runtime.

Callers use get_answerer()/get_verifier() (never a captured object) so that a
settings change can swap in freshly-built agents via rebuild(). The agents bind
the current LLM client + chat model from the factory at build time.
"""
from __future__ import annotations
from agents import Agent, ModelSettings
from ..core import settings
from ..core.prompts import VERIFIER_INSTRUCTIONS, VERDICT_JSON_SHAPE
from ..llm.factory import chat_model
from .answerer import ANSWERER_INSTRUCTIONS, search_knowledge_base, corpus_overview

_answerer: Agent | None = None
_verifier: Agent | None = None


def rebuild() -> None:
    """Re-create both agents from current settings (call after a settings change)."""
    global _answerer, _verifier
    temp = float(settings.get().get("temperature", 0.1))
    _answerer = Agent(
        name="Enterprise RAG Assistant", instructions=ANSWERER_INSTRUCTIONS,
        model=chat_model(), model_settings=ModelSettings(temperature=temp),
        tools=[search_knowledge_base, corpus_overview])
    _verifier = Agent(
        name="Grounding Verifier",
        instructions=(VERIFIER_INSTRUCTIONS + "\n\nRespond with ONE JSON object and "
                      "NOTHING else (no prose, no Markdown, no code fences). Use exactly "
                      "this shape:\n" + VERDICT_JSON_SHAPE),
        model=chat_model(),
        model_settings=ModelSettings(temperature=0.0,
                                     extra_body={"response_format": {"type": "json_object"}}),
        tools=[])


def get_answerer() -> Agent:
    if _answerer is None:
        rebuild()
    return _answerer


def get_verifier() -> Agent:
    if _verifier is None:
        rebuild()
    return _verifier
