"""Document upload handling: decode uploaded files and index them into STORE.

Accepts any UTF-8-ish plain text (the store is document-agnostic). Returns a
per-file summary so the UI can show what was indexed.
"""
from __future__ import annotations
from ..retrieval.store import STORE
from ..storage import documents as docstore


async def index_upload(filename: str, raw: bytes, persist: bool = True) -> dict:
    """Decode one uploaded file, add it to the store, and persist its text so it
    survives restarts. Returns a status dict."""
    try:
        text = raw.decode("utf-8", errors="ignore")
    except Exception as err:                               # pragma: no cover - defensive
        return {"filename": filename, "chunks": 0, "error": str(err)}
    if not text.strip():
        return {"filename": filename, "chunks": 0, "error": "empty file"}
    chunks = await STORE.add(filename, text)
    if persist:
        docstore.save(filename, text)                      # survive restarts
    return {"filename": filename, "chunks": chunks, "error": None}


def store_status() -> dict:
    """Current index size — drives the UI's 'documents ready' indicator."""
    return {
        "records": len(STORE.titles),
        "chunks": len(STORE.chunks),
        "ready": len(STORE.chunks) > 0,
    }


def list_documents() -> list[dict]:
    """All indexed files with their record/chunk counts (for the Documents modal)."""
    return STORE.documents()


def remove_document(source: str) -> bool:
    """Remove one indexed file by its source name (and forget it from storage)."""
    docstore.delete(source)                                # don't restore on next boot
    return STORE.remove(source)


async def restore_documents() -> int:
    """Re-index every persisted document into the store (called at startup)."""
    count = 0
    for source, content in docstore.all_documents():
        await STORE.add(source, content)
        count += 1
    return count
