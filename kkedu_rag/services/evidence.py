"""Evidence assembly for a turn: what the verifier is allowed to ground against.

``collect_evidence`` harvests the exact tool outputs the answerer saw (no extra
retrieval); ``ensure_overview`` guarantees the corpus overview is present for
aggregate/list/count questions; ``recent_context`` pulls a few prior turns as
referents only (never evidence).
"""
from __future__ import annotations
import re
from agents import ToolCallOutputItem, SQLiteSession
from ..retrieval.store import STORE

# Aggregate/list/count intent -> guarantee the overview is in the evidence.
_AGG_RE = re.compile(r"\b(how many|list all|list every|list the|all of|total|"
                     r"count|overview|every|number of|how much)\b", re.I)


def collect_evidence(result) -> str:
    """The exact tool outputs the answerer saw this turn (no extra retrieval)."""
    parts = [str(it.output) for it in result.new_items
             if isinstance(it, ToolCallOutputItem)]
    seen, uniq = set(), []                                # dedupe re-queried blocks
    for p in parts:
        if p not in seen:
            seen.add(p)
            uniq.append(p)
    return "\n\n---\n\n".join(uniq)


def ensure_overview(question: str, evidence: str) -> str:
    """For aggregate/list/count questions, guarantee the overview is present even
    if the answerer skipped that tool. overview() is a pure local call (no LLM)."""
    if _AGG_RE.search(question) and "Total indexed records" not in evidence:
        ov = STORE.overview()
        evidence = (evidence + "\n\n---\n\n" + ov) if evidence.strip() else ov
    return evidence


async def recent_context(session: SQLiteSession, n: int = 3) -> str:
    """A few prior turns, for the verifier to resolve what a question refers to.
    Used ONLY as referents — never as evidence."""
    items = await session.get_items(limit=n + 1)           # +1: drop the current user turn
    lines = []
    for it in items[:-1] if items else []:
        role = it.get("role", "")
        content = it.get("content", "")
        if isinstance(content, list):                      # multipart -> join text parts
            content = " ".join(p.get("text", "") for p in content if isinstance(p, dict))
        if role in ("user", "assistant") and content:
            lines.append(f"{role}: {content}")
    return "\n".join(lines)
