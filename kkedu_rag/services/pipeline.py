"""The single-turn RAG pipeline: answerer -> grounding verifier -> memory.

Orchestrates one question end to end and keeps conversation memory consistent
with what the user actually saw (if the verifier replaces the draft, the stored
assistant turn is swapped to match).
"""
from __future__ import annotations
from agents import Runner, SQLiteSession
from ..agents.wiring import get_answerer, get_verifier
from ..core.sanitize import sanitize, strip_harmony
from ..verification import parse_verdict, honor_correction
from .evidence import collect_evidence, ensure_overview, recent_context


async def _verify(question: str, draft: str, evidence: str, ctx: str) -> str:
    """Run the verifier; return its corrected answer only if proven, else draft."""
    vinput = (f"CONTEXT (referents only, NOT evidence):\n{ctx}\n\n"
              f"QUESTION:\n{question}\n\n"
              f"EVIDENCE (the ONLY ground truth):\n{evidence}\n\n"
              f"DRAFT (verify this):\n{draft}")
    try:
        vres = await Runner.run(get_verifier(), vinput)    # the ONE extra LLM call (stateless)
        verdict = parse_verdict(vres.final_output)
        if honor_correction(verdict, draft, evidence):
            return strip_harmony(verdict.corrected_answer)  # safe-half clean only
    except Exception as err:                               # fail-open, but LOUD (never silent)
        print(f"[verifier skipped: {err}]")
    return draft


async def answer_turn(session: SQLiteSession, question: str) -> str:
    """Answer one question and persist the shown reply to conversation memory."""
    ctx = await recent_context(session)                    # referents BEFORE this turn is stored
    result = await Runner.run(get_answerer(), question, session=session)
    draft = sanitize(result.final_output)                  # answerer gets full sanitize
    evidence = ensure_overview(question, collect_evidence(result))
    answer = await _verify(question, draft, evidence, ctx) if evidence.strip() else draft
    if answer != draft:                                    # verifier replaced the draft
        await session.pop_item()                           # drop the stored draft...
        await session.add_items([{"role": "assistant", "content": answer}])  # ...store shown
    return answer
