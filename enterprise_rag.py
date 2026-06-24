"""Backward-compatible launcher for the refactored package.

The implementation now lives in the ``kkedu_rag`` package (layered modules under
kkedu_rag/). This shim preserves the original ``python enterprise_rag.py <docs>``
invocation; the canonical entrypoint is ``python -m kkedu_rag <docs>``.
"""
from __future__ import annotations
import asyncio
from kkedu_rag.cli import main

if __name__ == "__main__":
    asyncio.run(main())
