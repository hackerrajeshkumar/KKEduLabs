"""Corpus-level overview: the grounding evidence for counting/listing questions.

Pure function over the store's three parallel lists. Fully document-agnostic:
groups titles by whatever type each record declares, and surfaces stated
'label: number' figures verbatim. If records carry no type label, it says so
plainly rather than inventing a grouping.
"""
from __future__ import annotations
import re


def build_overview(titles: list[str], type_labels: list[str], chunks: list[str]) -> str:
    """Total record count, titles grouped by declared type, and stated figures."""
    n_records = len(titles)
    # Group record titles by the kind each record declares for itself.
    groups: dict[str, list[str]] = {}
    for i, title in enumerate(titles):
        label = (type_labels[i] if i < len(type_labels) else "").strip()
        name = title if title else f"(untitled record {i + 1})"
        groups.setdefault(label, []).append(name)

    out = [f"Total indexed records (documents/sections): {n_records}"]
    has_grouping = any(lbl for lbl in groups)             # at least one stated type
    if has_grouping:
        out.append("Record titles grouped by the type/category each record "
                   "states for itself (with the count per group). Use these "
                   "groups to tell different kinds of record apart:")
        for label in sorted(groups, key=lambda l: (l == "", l)):
            head = label if label else "(no stated type)"
            items = groups[label]
            out.append(f"- {head} [{len(items)} record(s)]:\n  - " + "\n  - ".join(items))
    else:                                                 # no grouping signal exists
        names = [t if t else f"(untitled record {i + 1})"
                 for i, t in enumerate(titles)]
        out.append("Record titles (the corpus does NOT classify these into "
                   "types, so membership in any category cannot be confirmed "
                   "from structure):\n- " + "\n- ".join(names))

    # Surface any concise line pairing a label with a number, e.g.
    # "No. of Institutions: 25", "Record count: 23", "Total Employees 1,200".
    stat_re = re.compile(r"^.{0,40}?[:\-]?\s*[\d][\d,]*\b")
    stats = sorted({
        s for c in chunks for raw in c.splitlines()
        if (s := raw.strip()) and len(s) <= 60 and stat_re.match(s)
        and any(ch.isalpha() for ch in s)                 # must have a label, not bare number
    })
    if stats:
        out.append("Explicit figures stated verbatim in the corpus (each shown "
                   "WITH its label; quote exactly, do not recompute):\n- "
                   + "\n- ".join(stats))
    return "\n\n".join(out)
