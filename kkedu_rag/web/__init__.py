"""Web layer: a FastAPI app exposing the RAG pipeline as a streaming chat API.

Real-time token streaming over Server-Sent Events, document upload into the
store, and persistent conversation memory — wired to the same agents/retrieval/
verification stack the CLI uses. Run with ``python -m kkedu_rag.web`` or the
``kkedu-rag-web`` console script.
"""
