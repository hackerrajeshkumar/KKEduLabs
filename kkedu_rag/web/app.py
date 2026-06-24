"""FastAPI application: mounts the API routes and serves the chat UI.

Run with ``python -m kkedu_rag.web`` or the ``kkedu-rag-web`` console script.
Optionally pass document paths as CLI args to pre-index them at startup.
"""
from __future__ import annotations
import sys
import asyncio
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from .routes import router
from .settings_routes import router as settings_router
from .users_routes import router as users_router

_STATIC = Path(__file__).parent / "static"

app = FastAPI(title="KKEdu RAG", version="1.0.0")
app.include_router(router)
app.include_router(settings_router)
app.include_router(users_router)
app.mount("/static", StaticFiles(directory=_STATIC), name="static")


@app.get("/")
async def index() -> FileResponse:
    """Serve the single-page chat UI."""
    return FileResponse(_STATIC / "index.html")


def run() -> None:
    """Console entrypoint: pre-index any CLI-passed docs, then serve.

    Host/port are configurable via KKEDU_HOST / KKEDU_PORT (default 0.0.0.0:7007).
    """
    import os
    import uvicorn
    from .documents import restore_documents

    async def _boot():
        from ..storage import users
        users.seed_default_admin()                         # ensure an admin exists
        n = await restore_documents()                      # re-index persisted docs
        if n:
            print(f"Restored {n} persisted document(s) from rag.db")
        docs = [a for a in sys.argv[1:] if not a.startswith("-")]
        for path in docs:                                  # CLI docs: index + persist
            try:
                from .documents import index_upload
                with open(path, "rb") as f:
                    await index_upload(os.path.basename(path), f.read())
            except OSError as err:
                print(f"  skip {path}: {err}")
    asyncio.run(_boot())
    host = os.environ.get("KKEDU_HOST", "0.0.0.0")
    port = int(os.environ.get("KKEDU_PORT", "7007"))
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    run()
