"""Stateless retrieval primitives: tokenizing, record parsing, chunking, BM25.

Free functions with no instance state — unit-testable in isolation. ``store``
composes them; they never import ``store`` (one-way dependency, no cycle).
"""
from __future__ import annotations
import math
import re
from collections import Counter
from ..core.config import CHUNK_SIZE, CHUNK_OVERLAP

# Common English words carry no retrieval signal; dropping them from the QUERY
# lets rare, meaningful terms (names, titles, IDs) dominate keyword matching.
STOPWORDS = frozenset(
    "a an the is are was were be been being of in on at to for from by with "
    "and or but if then else as this that these those it its he she they we "
    "you i me my our your their what which who whom whose when where why how "
    "do does did done has have had can could will would shall should may "
    "might must about into over under than there here all any each more most "
    "no not only own same so some such".split())

# Header fields (any one) a record may use to declare its own kind/group.
# Read generically — whatever the document states, no domain assumptions.
TYPE_FIELDS = ("category:", "type:", "section:", "kind:", "group:")


def tokenize(text: str) -> list[str]:
    """Lowercase word/number tokens — the unit of lexical (keyword) matching."""
    return re.findall(r"[a-z0-9]+", text.lower())


def parse_records(text: str) -> list[tuple[str, str, str]]:
    """Split a document into (title, type_label, body) records. Understands the
    cleaned '=== DOCUMENT START ===' layout; falls back to one untitled record.
    type_label is whatever category/type/section field the record declares ("" if
    none) — used purely to group like records, no hardcoding."""
    marker = "=== DOCUMENT START ==="
    has_marker = marker in text
    blocks = text.split(marker) if has_marker else [text]
    out: list[tuple[str, str, str]] = []
    for b in blocks:
        b = b.replace("=== DOCUMENT END ===", "").strip()
        if not b:
            continue
        title = next((ln.split(":", 1)[1].strip() for ln in b.splitlines()
                      if ln.lower().startswith("title:")), "")
        type_label = next((ln.split(":", 1)[1].strip() for ln in b.splitlines()
                           if ln.lower().startswith(TYPE_FIELDS)), "")
        # In a marker-delimited file, a block with no title/type and no 'text:'
        # body is the file preamble (header), not a record — skip it.
        if has_marker and not title and not type_label and "text:" not in b.lower():
            continue
        out.append((title, type_label, b.split("text:", 1)[-1].strip()))
    return out


def chunk(title: str, body: str) -> list[str]:
    """Slide a fixed window over a record body, tagging each chunk with its title."""
    step = CHUNK_SIZE - CHUNK_OVERLAP
    parts = [body[i:i + CHUNK_SIZE] for i in range(0, len(body), step)]
    tag = f"[{title}]\n" if title else ""       # carry record context per chunk
    return [tag + p.strip() for p in parts if p.strip()]


def bm25_scores(query: str, n: int, tokens: list[Counter], df: Counter) -> list[float]:
    """BM25 keyword scores over all chunks — catches exact terms (names, titles,
    IDs) that semantic search ranks low. Returns one score per chunk."""
    scores = [0.0] * n
    terms = set(tokenize(query)) - STOPWORDS           # keep meaningful terms
    if not terms:                                      # query was all stopwords
        terms = set(tokenize(query))                   # fall back to raw tokens
    if not terms or n == 0:
        return scores
    avgdl = (sum(sum(tf.values()) for tf in tokens) / n) or 1.0
    k1, b = 1.5, 0.75                                  # standard BM25 constants
    for term in terms:
        d = df.get(term, 0)
        if d == 0:
            continue
        idf = math.log(1 + (n - d + 0.5) / (d + 0.5))  # rarer term -> higher idf
        for i, tf in enumerate(tokens):
            f = tf.get(term, 0)
            if f:
                dl = sum(tf.values())
                scores[i] += idf * (f * (k1 + 1)) / (f + k1 * (1 - b + b * dl / avgdl))
    return scores


def min_max_norm(a: list[float]) -> list[float]:
    """Min-max to [0,1] so semantic and lexical scores blend on one scale."""
    if not a:
        return []
    lo, hi = min(a), max(a)
    if hi > lo:
        return [(v - lo) / (hi - lo) for v in a]
    return [0.0] * len(a)
