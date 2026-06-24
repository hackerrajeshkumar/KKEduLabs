"""Document ingestion: expand glob patterns, read files, index into the store."""
from __future__ import annotations
import sys
import glob
from ..retrieval.store import STORE


async def ingest(patterns: list[str]) -> None:
    """Index every file matching the given glob patterns into the store."""
    paths: list[str] = []
    for pat in patterns:
        paths += glob.glob(pat)
    if not paths:
        sys.exit("No files matched. Pass text files, e.g. python -m kkedu_rag notes.txt")
    print("Indexing documents...")
    for path in paths:
        try:
            text = open(path, encoding="utf-8", errors="ignore").read()
        except OSError as err:
            print(f"  skip {path}: {err}")
            continue
        print(f"  indexed {path}: {await STORE.add(path, text)} chunks")
