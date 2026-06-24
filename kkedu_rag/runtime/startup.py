"""Import-time global side-effects: SDK tracing off + stdout Unicode shim.

Importing this module performs the bootstrap. ``llm.ollama`` imports it before
constructing the client, so the effects are guaranteed to run before any Agent
or print — deterministic ordering, not import luck.
"""
from __future__ import annotations
import sys
from agents import set_tracing_disabled

set_tracing_disabled(True)           # no OpenAI key -> disable trace upload

try:                                 # render Unicode safely on legacy consoles
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
