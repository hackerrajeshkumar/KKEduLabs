"""Runtime bootstrap: import-time global side-effects, owned in one place.

Importing ``runtime.startup`` disables SDK trace upload and makes stdout
tolerant of Unicode. ``llm.ollama`` imports it before constructing the client so
the effects fire before any Agent exists.
"""
