"""Core: framework-free building blocks shared across the app.

Settings (``config``), output cleanup (``sanitize``), and prompt templates
(``prompts``). All pure — no SDK, no I/O, no singletons — so every other layer
may import from here without risk of a cycle.
"""
