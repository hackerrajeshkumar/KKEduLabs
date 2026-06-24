"""LLM access layer: the shared Ollama client singleton.

Import the rebuildable client/model from ``kkedu_rag.llm.factory`` (``client()``,
``chat_model()``, ``rebuild()``). Kept out of this init so touching the package
never forces the openai import chain prematurely.
"""
