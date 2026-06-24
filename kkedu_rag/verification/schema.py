"""The verdict schema the verifier emits, plus tolerant JSON parsing.

Pure pydantic + stdlib + the sanitize util — no SDK, no STORE, so it can never
close an import cycle.
"""
from __future__ import annotations
import re
from typing import Literal
from pydantic import BaseModel, Field
from ..core.sanitize import strip_harmony


class ClaimCheck(BaseModel):
    """One atomic factual claim from the draft, re-derived against the evidence."""
    claim: str
    status: Literal["supported", "unsupported", "contradicted", "needs_inference"]
    evidence_quote: str = ""             # verbatim span proving supported/contradicted; else ""


class Defect(BaseModel):
    kind: Literal[
        "unsupported_claim", "contradiction", "count_inconsistency",
        "category_mismatch", "omission", "miscitation", "needs_inference",
        "insufficient_evidence",
    ]
    detail: str
    evidence_quote: str = ""             # verbatim proof; "" allowed only for omission/insufficient


class Verdict(BaseModel):
    verdict: Literal["approve", "correct"]
    claim_checks: list[ClaimCheck] = Field(default_factory=list)
    defects: list[Defect] = Field(default_factory=list)
    corrected_answer: str = ""           # full replacement; non-empty iff verdict=="correct"
    removed_content_note: str = ""       # justify any draft content the correction drops
    notes: str = ""


def parse_verdict(raw: str) -> Verdict:
    """Parse the verifier's reply into a Verdict. Tolerates code fences, a little
    surrounding prose (extract the outermost JSON object), and the occasional
    trailing comma gpt-oss emits in long objects."""
    text = strip_harmony(raw).strip()
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.MULTILINE).strip()
    if not text.startswith("{"):                         # carve out the JSON object
        i, j = text.find("{"), text.rfind("}")
        if i != -1 and j != -1 and j > i:
            text = text[i:j + 1]
    try:
        return Verdict.model_validate_json(text)
    except ValueError:                                   # tolerate trailing commas
        repaired = re.sub(r",\s*([}\]])", r"\1", text)
        return Verdict.model_validate_json(repaired)
