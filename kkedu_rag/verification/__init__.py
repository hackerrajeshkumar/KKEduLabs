"""Verification subpackage: the grounding contract and its enforcement.

``schema`` holds the verdict models + JSON parsing; ``guards`` holds the
code-enforced acceptance gate. Re-exported here for ergonomic imports
(``from kkedu_rag.verification import Verdict, parse_verdict, honor_correction``)
— safe because this subpackage is pure (pydantic + stdlib + sanitize), so it
cannot participate in an import cycle.
"""
from __future__ import annotations
from .schema import ClaimCheck, Defect, Verdict, parse_verdict
from .guards import honor_correction

__all__ = ["ClaimCheck", "Defect", "Verdict", "parse_verdict", "honor_correction"]
