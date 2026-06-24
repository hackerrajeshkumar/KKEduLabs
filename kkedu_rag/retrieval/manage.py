"""Document management over a VectorStore: list indexed files and remove one.

Free functions that operate on the store's parallel arrays, keeping store.py
focused on add/search. Removal drops every chunk/title for a source and rebuilds
the document-frequency table so retrieval stays consistent.
"""
from __future__ import annotations
from collections import Counter


def list_documents(store) -> list[dict]:
    """One entry per indexed file: name, record count, chunk count."""
    out: dict[str, dict] = {}
    for src in store.title_origin:
        out.setdefault(src, {"source": src, "records": 0, "chunks": 0})["records"] += 1
    for src in store.chunk_origin:
        if src in out:
            out[src]["chunks"] += 1
    return list(out.values())


def remove_document(store, source: str) -> bool:
    """Drop every chunk/title belonging to one source file; rebuild the index."""
    if source not in store.chunk_origin and source not in store.title_origin:
        return False
    keep = [i for i, s in enumerate(store.chunk_origin) if s != source]
    store.chunks = [store.chunks[i] for i in keep]
    store.sources = [store.sources[i] for i in keep]
    store.tokens = [store.tokens[i] for i in keep]
    store.chunk_origin = [store.chunk_origin[i] for i in keep]
    store.matrix = store.matrix[keep] if store.matrix is not None and keep else None
    tkeep = [i for i, s in enumerate(store.title_origin) if s != source]
    store.titles = [store.titles[i] for i in tkeep]
    store.type_labels = [store.type_labels[i] for i in tkeep]
    store.title_origin = [store.title_origin[i] for i in tkeep]
    store.df = Counter()                               # rebuild document frequencies
    for tf in store.tokens:
        store.df.update(tf.keys())
    return True
