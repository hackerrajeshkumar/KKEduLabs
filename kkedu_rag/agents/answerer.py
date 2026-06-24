"""The answerer's instructions and its two function tools.

The agent object itself is built by ``registry`` (so it can be rebuilt live when
settings change); this module owns the stable parts: the tool implementations
(which call the STORE singleton) and the instruction text.
"""
from __future__ import annotations
from agents import function_tool
from ..retrieval.store import STORE
from ..retrieval.scope import get_sources


@function_tool
async def search_knowledge_base(query: str) -> str:
    """Search the attached documents and return the most relevant passages with
    their source titles. Use for specific content questions."""
    return await STORE.search(query, sources=get_sources())


@function_tool
async def corpus_overview() -> str:
    """Return corpus-level facts: how many records are indexed, the full list of
    record titles grouped by whatever type/category each record states, and any
    explicit aggregate figures the documents state verbatim. Use this for 'how
    many', counting, listing, or 'what documents do you have' questions."""
    return STORE.overview()


ANSWERER_INSTRUCTIONS = """
You are KKEdu RAG.

Answer only from attached documents.

Guidelines:

1. For greetings or conversational messages:
   - Do not call tools.
   - Reply briefly and invite document questions.

2. For document questions:
   - Use search_knowledge_base.
   - If results are insufficient, retry with a better query.

3. For counts, totals, listings, or corpus summaries:
   - Use corpus_overview.
   - Use only the figures returned.
   - Never calculate counts yourself.

4. If information is not found after reasonable retrieval attempts:
   - Say the documents do not contain that information.

5. Cite source titles naturally in the answer.

Respond in Markdown.
"""