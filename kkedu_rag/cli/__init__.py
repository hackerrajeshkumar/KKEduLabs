"""Interface layer: the interactive REPL.

Exposes ``main`` (the async entrypoint) so the package root and __main__ can run
it without reaching into the concrete module.
"""
from __future__ import annotations
from .repl import main

__all__ = ["main"]
