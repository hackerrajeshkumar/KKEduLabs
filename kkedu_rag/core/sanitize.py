"""Strip gpt-oss 'harmony' formatting artifacts from model output.

gpt-oss interleaves control tokens (<|channel|>, <|message|>, commentary/analysis
channels, tool-call markers) and sometimes glues raw tool names on as a
pseudo-citation; these occasionally leak through the Ollama OpenAI-compat path.
These pure, dependency-free functions remove them so the user only sees clean
text. Cross-cutting utility, used by both verification and the pipeline.
"""
from __future__ import annotations
import re

_HARMONY_TOKENS = re.compile(
    r"<\|(?:channel|message|constrain|start|end|call|return|system|"
    r"developer|user|assistant)\|>")
# Channel preambles gpt-oss leaks, e.g. 'commentary to=functions.foo json {}',
# 'analysis ...', or a bare 'to=functions.xxx' tail once tokens are stripped.
_CHANNEL_PREAMBLE = re.compile(
    r"(?:commentary|analysis|final)?\s*to=\S+", re.IGNORECASE)
_LEFTOVER = re.compile(r"\b(?:commentary|analysis)\b\s*|\bjson\b\s*\{\s*\}|\{\s*\}")
# Raw tool-function names the model sometimes glues on as a pseudo-citation
# (e.g. '**25 institutions**corpus_overview'). Strip the bare identifier only —
# never ordinary words like "overview". Optionally preceded by 'per the'.
_TOOL_LEAK = re.compile(
    r"\s*(?:per\s+(?:the\s+)?)?\b(?:corpus_overview|search_knowledge_base)\b")


def strip_harmony(text: str) -> str:
    """Remove only gpt-oss control tokens / channel preambles / leaked tool names.
    No footnote-digit stripping — safe on text that may legitimately contain
    numbers (e.g. the verifier's corrected answer)."""
    if not text:
        return text
    text = re.sub(r"【[^】]*】", "", text)              # strip full fancy citation markers
    text = re.sub(r"\[\d+\]", "", text)               # strip standard numeric citations
    text = _HARMONY_TOKENS.sub("", text)           # <|channel|>, <|message|>, ...
    text = _CHANNEL_PREAMBLE.sub("", text)         # 'commentary to=functions.x'
    text = _LEFTOVER.sub("", text)                 # trailing 'json {}' / bare {}
    text = _TOOL_LEAK.sub("", text)                # '...**corpus_overview' citation leak
    return text.strip()


def sanitize(text: str) -> str:
    """Full clean for the raw ANSWERER stream: strip_harmony() plus removal of a
    dangling footnote digit glued to a closing '**' (e.g. 'Name**1'). The letter
    look-behind means a bolded number like '**25**' is never touched."""
    text = strip_harmony(text)
    if not text:
        return text
    text = re.sub(r"(?<=[A-Za-z])(\*\*)(\d{1,2})(?=\s|$|[.,;:])", r"\1", text)
    return text.strip()
