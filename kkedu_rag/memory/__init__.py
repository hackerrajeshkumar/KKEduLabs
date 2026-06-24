"""Memory layer: persistent conversation history via the SDK session store.

Owns construction of the SQLite-backed conversation session. Import the factory:
``from kkedu_rag.memory.session import open_session``.
"""
