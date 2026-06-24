"""Code-enforced acceptance gate for verifier corrections.

The real safety layer: a proposed correction is accepted only if it is PROVEN
(a verbatim-quoted or legitimately quote-less defect) and NON-FABRICATING
(introduces no new number/name, drops no evidence-backed figure unjustified).
Decided in code, never on the model's self-reported confidence.
"""
from __future__ import annotations
import re
import difflib
from .schema import Verdict


def _canon(s: str) -> str:
    s = re.sub(r"^[\s\-\*•]+", "", s.strip())             # drop list markers
    return re.sub(r"\s+", " ", s).lower()


def _quote_in_evidence(quote: str, evidence: str) -> bool:
    q, ev = _canon(quote), _canon(evidence)
    if not q:
        return False
    if q in ev:
        return True
    m = difflib.SequenceMatcher(None, q, ev).find_longest_match(0, len(q), 0, len(ev))
    return m.size >= max(8, int(0.9 * len(q)))            # tolerate cosmetic reformatting


_NUM = re.compile(r"\d[\d,]*")
# Multi-word Capitalized phrase (proper-noun-ish): used to detect invented names.
_PROPER = re.compile(r"\b([A-Z][\w&.-]+(?:\s+[A-Z][\w&.-]+)+)\b")
_WORD = re.compile(r"[a-z0-9]+")


def _nums(s: str) -> set[str]:
    return {n.replace(",", "") for n in _NUM.findall(s)}


def _fabricated_names(correction: str, evidence: str) -> list[str]:
    """Proper-noun phrases in the correction the evidence cannot back. A phrase
    is fabricated only if it has a significant word (len>=3, not a digit) absent
    from the evidence's whole word set — robust to punctuation/tokenization
    differences (e.g. 'Velammal New-Gen Kids' vs the comma-suffixed form)."""
    ev_words = set(_WORD.findall(evidence.lower()))
    bad = []
    for phrase in _PROPER.findall(correction):
        sig = [w for w in _WORD.findall(phrase.lower()) if len(w) >= 3 and not w.isdigit()]
        if sig and any(w not in ev_words for w in sig):
            bad.append(phrase)
    return bad


def honor_correction(v: Verdict, draft: str, evidence: str) -> bool:
    """Accept a correction only if proven and non-fabricating (see module doc)."""
    if v.verdict != "correct" or not v.corrected_answer.strip():
        return False
    # (a) Require at least one PROVEN defect — backed by a verbatim quote, or one
    #     of the two legitimately quote-less kinds. A proven defect IS the
    #     real-problem signal (the verifier sometimes records it only in
    #     defects[]); no proven defect -> nothing to fix -> reject cosmetic churn.
    if not any(d.kind in ("omission", "insufficient_evidence")
               or _quote_in_evidence(d.evidence_quote, evidence) for d in v.defects):
        return False
    corr = v.corrected_answer
    # (b) anti-fabrication: introduce no NEW number, no proper-noun phrase whose
    #     significant words are absent from the evidence.
    if _nums(corr) - _nums(evidence):
        return False
    if _fabricated_names(corr, evidence):
        return False
    # (c) no-deletion: a figure verbatim in BOTH draft and evidence must survive,
    #     unless the verifier justifies the change in removed_content_note.
    dropped = (_nums(draft) & _nums(evidence)) - _nums(corr)
    if dropped and not v.removed_content_note.strip():
        return False
    return True
