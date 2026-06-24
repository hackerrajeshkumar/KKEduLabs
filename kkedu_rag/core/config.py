"""Configuration constants for the RAG application (no side-effects).

Pure values only — import-time side-effects (SDK tracing, stdout shim) live in
``runtime.startup`` so importing settings never silently mutates global state.
"""
from __future__ import annotations

# ---- Ollama / model wiring -------------------------------------------------
OLLAMA_BASE_URL = "http://localhost:11434/v1"   # Ollama's OpenAI-compatible API
CHAT_MODEL = "gpt-oss:20b-cloud"     # reasoning + tool-calling model (Ollama cloud)
EMBED_MODEL = "nomic-embed-text"     # 768-dim embeddings (Ollama)

# ---- Retrieval tuning ------------------------------------------------------
CHUNK_SIZE, CHUNK_OVERLAP = 1000, 200  # characters per chunk / overlap
TOP_K = 15                           # passages returned per search (hybrid recall)
CANDIDATE_POOL = 40                  # chunks scored by each retriever before fusing
LEXICAL_WEIGHT = 0.45                # 0=pure semantic, 1=pure keyword; blend of both
EMBED_BATCH = 64                     # chunks per embeddings request
# nomic-embed-text is trained with task prefixes; using them sharply lifts recall
DOC_PREFIX, QUERY_PREFIX = "search_document: ", "search_query: "

# ---- Conversation memory ---------------------------------------------------
MEMORY_DB = "rag_memory.db"          # SQLite file backing conversation memory
SESSION_ID = "default"               # conversation id within the memory store
