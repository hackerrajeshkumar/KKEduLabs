"""Runtime LLM/retrieval/vector settings — persisted to JSON, editable via the UI.

Seeded from the static config defaults, then overlaid with anything saved to
settings.json. ``get()`` returns the live dict; ``update()`` merges a patch and
persists. The LLM factory reads these to (re)build the client and agents, so
edits can be applied live.
"""
from __future__ import annotations
import json
from pathlib import Path
from . import config

_PATH = Path("settings.json")

_DEFAULTS = {
    "chat_model": config.CHAT_MODEL,
    "embed_model": config.EMBED_MODEL,
    "ollama_base_url": config.OLLAMA_BASE_URL,
    "api_key": "ollama",
    "temperature": 0.1,
    # retrieval / vector store
    "top_k": config.TOP_K,
    "lexical_weight": config.LEXICAL_WEIGHT,
    "chunk_size": config.CHUNK_SIZE,
    "chunk_overlap": config.CHUNK_OVERLAP,
    "vector_backend": "in-memory (numpy hybrid BM25 + cosine)",
    "embed_dim": 768,
}

_state: dict = {}


def _load() -> dict:
    data = dict(_DEFAULTS)
    if _PATH.exists():
        try:
            data.update(json.loads(_PATH.read_text(encoding="utf-8")))
        except Exception:
            pass
    return data


def get() -> dict:
    """The current effective settings (lazily loaded once)."""
    if not _state:
        _state.update(_load())
    return dict(_state)


def update(patch: dict) -> dict:
    """Merge a patch into settings, persist to disk, and return the new state."""
    cur = get()
    cur.update({k: v for k, v in patch.items() if k in _DEFAULTS})
    _state.clear()
    _state.update(cur)
    _PATH.write_text(json.dumps(cur, indent=2), encoding="utf-8")
    return dict(cur)
