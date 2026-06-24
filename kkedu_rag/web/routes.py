"""HTTP API: streaming chat, document upload/remove, and persistent chat threads.

Each conversation is a thread whose id doubles as the SDK session id — messages
persist in the session store, thread metadata (title/timestamps) in SQLite. The
sidebar lists threads; opening one returns its full message history.
"""
from __future__ import annotations
import json
from fastapi import APIRouter, UploadFile, File
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel
from ..memory.session import open_session
from ..storage import conversations as convo
from .documents import (index_upload, store_status, list_documents,
                        remove_document)
from .streaming import stream_turn

router = APIRouter(prefix="/api")


class ChatRequest(BaseModel):
    message: str
    conversation_id: str | None = None   # which thread; created if omitted
    sources: list[str] | None = None     # scope to these files; None/empty = all


class RemoveRequest(BaseModel):
    source: str


def _sse(event: dict) -> str:
    return f"data: {json.dumps(event)}\n\n"


@router.post("/chat")
async def chat(req: ChatRequest):
    """Stream the answer for one question within a (new or existing) thread."""
    tid = req.conversation_id or convo.create()
    first = not convo.get(tid) or len(await open_session(tid).get_items(limit=1)) == 0
    session = open_session(tid)

    async def gen():
        yield _sse({"type": "meta", "conversation_id": tid})
        try:
            async for event in stream_turn(session, req.message, req.sources):
                yield _sse(event)
        except Exception as err:
            yield _sse({"type": "error", "text": str(err)})
        convo.touch(tid, title=req.message if first else None)   # title = first question
    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.get("/conversations")
async def conversations():
    """All chat threads, most recent first (for the sidebar history)."""
    return JSONResponse({"conversations": convo.list_all()})


@router.get("/conversations/{tid}")
async def conversation(tid: str):
    """One thread's full message history (to reopen it in the UI)."""
    items = await open_session(tid).get_items()
    msgs = []
    for it in items:
        role = it.get("role")
        if role not in ("user", "assistant"):
            continue
        content = it.get("content")
        if not content:
            continue
        if isinstance(content, list):
            text = "".join(p.get("text", "") for p in content if isinstance(p, dict))
            if not text.strip():
                continue
        elif isinstance(content, str):
            if not content.strip():
                continue
        msgs.append({"role": role, "content": content})
    return JSONResponse({"conversation": convo.get(tid), "messages": msgs})


@router.post("/conversations/{tid}/delete")
async def delete_conversation(tid: str):
    """Delete a thread and its stored messages."""
    await open_session(tid).clear_session()
    return JSONResponse({"deleted": convo.delete(tid)})


@router.post("/upload")
async def upload(files: list[UploadFile] = File(...)):
    results = [await index_upload(f.filename, await f.read()) for f in files]
    return JSONResponse({"results": results, "status": store_status()})


@router.get("/documents")
async def documents():
    return JSONResponse({"documents": list_documents(), "status": store_status()})


@router.post("/documents/remove")
async def remove(req: RemoveRequest):
    ok = remove_document(req.source)
    return JSONResponse({"removed": ok, "documents": list_documents(), "status": store_status()})


@router.get("/status")
async def status():
    return JSONResponse(store_status())
