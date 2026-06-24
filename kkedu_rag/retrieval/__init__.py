"""Retrieval subpackage: indexing helpers, corpus overview, and the store.

Deliberately empty (no re-exports). Consumers import the concrete module —
``from kkedu_rag.retrieval.store import STORE`` — so touching this package never
eagerly pulls the numpy/openai chain, and the init can never become a cycle hub.
"""
