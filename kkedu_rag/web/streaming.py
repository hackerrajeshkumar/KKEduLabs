"""Turn the SDK's run_streamed event firehose into clean UI events.

stream_turn() yields dicts the SSE layer serializes: token deltas as they arrive
(ChatGPT/Claude-style), tool-activity signals, then a final event carrying the
verifier-checked answer. The answerer's draft streams live; if the grounding
verifier later replaces it, a 'correction' event tells the UI to swap the text.
"""
from __future__ import annotations
from typing import AsyncGenerator
from agents import Runner, SQLiteSession, RawResponsesStreamEvent, RunItemStreamEvent
from openai.types.responses import ResponseTextDeltaEvent
from ..agents.wiring import get_answerer, get_verifier
from ..core.sanitize import sanitize, strip_harmony
from ..verification import parse_verdict, honor_correction
from ..services.evidence import collect_evidence, ensure_overview, recent_context
from ..retrieval.scope import set_sources

_TOOL_LABEL = {
    "search_knowledge_base": "Searching the documents",
    "corpus_overview": "Reading the corpus overview",
}


async def stream_turn(session: SQLiteSession, question: str,
                      sources: list[str] | None = None) -> AsyncGenerator[dict, None]:
    """Stream one Q&A turn as UI events. ``sources`` scopes retrieval to those
    files (None/empty = all). See module docstring for the contract."""
    set_sources(sources)                                   # scope this turn's retrieval
    ctx = await recent_context(session)                    # referents before this turn is stored
    result = Runner.run_streamed(get_answerer(), question, session=session)

    raw = ""                                               # accumulate raw draft for parity w/ CLI
    async for ev in result.stream_events():
        if isinstance(ev, RawResponsesStreamEvent) and isinstance(ev.data, ResponseTextDeltaEvent):
            delta = ev.data.delta or ""
            if delta:
                if not raw:
                    yield {"type": "tool", "label": ""}    # first token -> clear the tool chip
                raw += delta
                yield {"type": "token", "text": delta}     # live token to the client
        elif isinstance(ev, RunItemStreamEvent) and ev.name == "tool_called":
            tool = getattr(ev.item.raw_item, "name", "") or ""
            yield {"type": "tool", "label": _TOOL_LABEL.get(tool, f"Calling {tool}")}

    draft = sanitize(raw or result.final_output)           # clean the streamed draft
    evidence = ensure_overview(question, collect_evidence(result))
    if evidence.strip():
        yield {"type": "tool", "label": "Verifying answer"}   # distinct status during verify
    final = await _verified(session, question, draft, evidence, ctx)
    if final != draft:
        yield {"type": "correction", "text": final}        # verifier replaced the draft
    yield {"type": "done", "text": final}


async def _verified(session, question, draft, evidence, ctx) -> str:
    """Run the verifier; persist + return the corrected answer if proven, else draft."""
    if not evidence.strip():
        return draft
    vinput = (f"CONTEXT (referents only, NOT evidence):\n{ctx}\n\n"
              f"QUESTION:\n{question}\n\n"
              f"EVIDENCE (the ONLY ground truth):\n{evidence}\n\n"
              f"DRAFT (verify this):\n{draft}")
    try:
        vres = await Runner.run(get_verifier(), vinput)
        verdict = parse_verdict(vres.final_output)
        if honor_correction(verdict, draft, evidence):
            answer = strip_harmony(verdict.corrected_answer)
            await session.pop_item()                       # keep memory == shown answer
            await session.add_items([{"role": "assistant", "content": answer}])
            return answer
    except Exception as err:                               # fail-open, but logged
        print(f"[verifier skipped: {err}]")
    return draft
