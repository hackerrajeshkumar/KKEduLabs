"""Agent wiring: stable accessors over the live, rebuildable agent registry.

Callers import these functions (not captured objects) so a settings change can
swap in freshly-built agents. ``rebuild`` re-creates both from current settings.
"""
from __future__ import annotations
from .registry import get_answerer, get_verifier, rebuild
from .answerer import search_knowledge_base, corpus_overview

__all__ = ["get_answerer", "get_verifier", "rebuild",
           "search_knowledge_base", "corpus_overview"]
