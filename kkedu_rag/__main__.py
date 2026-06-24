"""Module entrypoint: ``python -m kkedu_rag report.txt notes/*.txt``."""
from __future__ import annotations
import asyncio
from .cli import main

if __name__ == "__main__":
    asyncio.run(main())
