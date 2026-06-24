"""Settings + model-discovery API: read/update LLM config and list Ollama models.

Updating settings persists them and rebuilds the LLM client + agents in place,
so a new chat model / host / embedding model takes effect immediately (no
restart). The model list is queried live from the configured Ollama host.
"""
from __future__ import annotations
import httpx
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from ..core import settings
from ..llm import factory
from ..agents import wiring

router = APIRouter(prefix="/api")


class SettingsPatch(BaseModel):
    chat_model: str | None = None
    embed_model: str | None = None
    ollama_base_url: str | None = None
    api_key: str | None = None
    temperature: float | None = None
    top_k: int | None = None
    lexical_weight: float | None = None
    chunk_size: int | None = None
    chunk_overlap: int | None = None
    vector_backend: str | None = None
    embed_dim: int | None = None


@router.get("/settings")
async def get_settings():
    """Current effective settings (LLM, retrieval, vector store)."""
    return JSONResponse(settings.get())


@router.put("/settings")
async def update_settings(patch: SettingsPatch):
    """Persist a settings patch and apply it live (rebuild client + agents)."""
    new = settings.update({k: v for k, v in patch.model_dump().items() if v is not None})
    factory.rebuild()                                     # new host/key -> new client
    wiring.rebuild()                                      # new model/temp -> new agents
    return JSONResponse({"ok": True, "settings": new})


@router.get("/models")
async def models():
    """List models installed on the configured Ollama host (live)."""
    base = settings.get()["ollama_base_url"].rsplit("/v1", 1)[0]
    try:
        async with httpx.AsyncClient(timeout=5) as c:
            data = (await c.get(f"{base}/api/tags")).json()
        names = sorted(m["name"] for m in data.get("models", []))
    except Exception as err:
        return JSONResponse({"models": [], "error": str(err)})
    return JSONResponse({"models": names, "current": settings.get()["chat_model"]})
