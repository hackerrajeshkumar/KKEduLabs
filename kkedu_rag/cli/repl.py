"""Enterprise RAG CLI — OpenAI Agents SDK + Ollama (gpt-oss).
Attach plain-text docs, then ask questions; an answerer agent replies strictly
from them via two function-calling tools (hybrid semantic+keyword search and a
grouped corpus overview) over local Ollama embeddings. A second grounding
VERIFIER agent audits each draft against the exact evidence and corrects
unsupported claims, inconsistent counts, and category-mismatched lists.
Conversation memory persists across turns/runs via the SDK SQLiteSession layer.
Setup: ollama pull gpt-oss:20b-cloud && ollama pull nomic-embed-text
       pip install -U openai-agents openai numpy pydantic
Run:   python -m kkedu_rag report.txt notes/*.txt
       ('exit' to quit, 'reset' to clear conversation memory)
"""
from __future__ import annotations
import sys
import asyncio
from ..retrieval.store import STORE
from ..memory.session import open_session
from ..services.ingestion import ingest
from ..services.pipeline import answer_turn


async def main() -> None:
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    await ingest(sys.argv[1:])
    session = open_session()                               # persistent conversation memory
    print(f"\nReady — {len(STORE.chunks)} chunks indexed. Ask a question "
          f"('exit' to quit, 'reset' to clear memory).\n")
    while True:
        try:
            question = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not question:
            continue
        if question.lower() in {"exit", "quit"}:
            break
        if question.lower() == "reset":                    # wipe conversation memory
            await session.clear_session()
            print("bot> memory cleared.\n")
            continue
        try:
            answer = await answer_turn(session, question)
        except Exception as err:                           # keep the REPL alive
            print(f"bot> error: {err}\n")
            continue
        print(f"\nbot> {answer}\n")


def run() -> None:
    """Synchronous console-script entrypoint (console scripts can't be async)."""
    asyncio.run(main())
