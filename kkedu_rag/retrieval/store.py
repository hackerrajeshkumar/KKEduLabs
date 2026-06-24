"""In-memory hybrid vector store + the process-wide STORE singleton.

The class stays whole: the index writer (``add``) and reader (``search``) live
together so the row-alignment invariant between chunks/tokens/df/matrix is
visible in one place. Stateless math is delegated to ``indexing``; the overview
string to ``overview``. Embeddings use the shared Ollama ``client``.
"""
from __future__ import annotations
from collections import Counter
import numpy as np
from ..core.config import EMBED_BATCH, DOC_PREFIX, QUERY_PREFIX, TOP_K, LEXICAL_WEIGHT
from ..core import settings
from ..llm.factory import client
from .indexing import parse_records, chunk, tokenize, bm25_scores, min_max_norm
from .overview import build_overview
from .manage import list_documents, remove_document


class VectorStore:
    """Cosine-similarity + BM25 hybrid search over Ollama embeddings (numpy)."""

    def __init__(self) -> None:
        self.chunks: list[str] = []
        self.sources: list[str] = []
        self.chunk_origin: list[str] = []    # bare source filename per chunk (for removal)
        self.titles: list[str] = []          # one per record, for corpus overview
        self.type_labels: list[str] = []     # parallel to titles: each record's stated kind
        self.title_origin: list[str] = []    # parallel to titles: which file each came from
        self.matrix: np.ndarray | None = None
        self.tokens: list[Counter] = []      # per-chunk term frequencies (lexical)
        self.df: Counter = Counter()         # document frequency per term (for idf)

    async def _embed(self, texts: list[str], prefix: str = "") -> np.ndarray:
        vecs: list[list[float]] = []
        model = settings.get()["embed_model"]
        for i in range(0, len(texts), EMBED_BATCH):        # batch large inputs
            batch = [prefix + t for t in texts[i:i + EMBED_BATCH]]
            resp = await client().embeddings.create(model=model, input=batch)
            vecs += [d.embedding for d in resp.data]
        m = np.asarray(vecs, dtype=np.float32)
        return m / (np.linalg.norm(m, axis=1, keepdims=True) + 1e-9)  # normalize

    async def add(self, source: str, text: str) -> int:
        # Idempotent by source: re-indexing a file replaces its prior records
        # instead of appending duplicates. Mirrors the persistence layer, where
        # `source` is the primary key (INSERT OR REPLACE). Without this, the boot
        # restore + a repeated add of the same file (CLI arg or re-upload) would
        # index every record twice.
        if source in self.title_origin or source in self.chunk_origin:
            self.remove(source)
        new, srcs = [], []
        for title, type_label, body in parse_records(text):
            self.titles.append(title)
            self.type_labels.append(type_label)
            self.title_origin.append(source)
            for c in chunk(title, body):
                new.append(c)
                srcs.append(f"{source}{' :: ' + title if title else ''}")
        if not new:
            return 0
        vecs = await self._embed(new, DOC_PREFIX)
        self.matrix = vecs if self.matrix is None else np.vstack([self.matrix, vecs])
        self.chunks += new
        self.sources += srcs
        self.chunk_origin += [source] * len(new)
        for c in new:                                  # build lexical index per chunk
            tf = Counter(tokenize(c))
            self.tokens.append(tf)
            self.df.update(tf.keys())                  # one count per distinct term
        return len(new)

    def documents(self) -> list[dict]:
        """One entry per indexed file: name, record count, chunk count."""
        return list_documents(self)

    def remove(self, source: str) -> bool:
        """Drop every chunk/title belonging to one source file; rebuild the index."""
        return remove_document(self, source)

    def overview(self) -> str:
        """Corpus-level facts for aggregate/counting/listing questions."""
        return build_overview(self.titles, self.type_labels, self.chunks)

    async def search(self, query: str, k: int = TOP_K,
                     sources: list[str] | None = None) -> str:
        if self.matrix is None:
            return "No documents are indexed."
        q = await self._embed([query], QUERY_PREFIX)
        semantic = self.matrix @ q[0]                      # cosine similarity
        lexical = bm25_scores(query, len(self.chunks), self.tokens, self.df)
        # fuse both, each normalized to [0,1], so neither scale dominates
        fused = (1 - LEXICAL_WEIGHT) * min_max_norm(semantic) + LEXICAL_WEIGHT * min_max_norm(lexical)
        if sources:                                        # scope to selected files only
            allowed = set(sources)
            mask = np.array([o in allowed for o in self.chunk_origin])
            if mask.any():
                fused = np.where(mask, fused, -1.0)        # exclude others
        top = np.argsort(fused)[::-1][:k]                  # descending top-k
        return "\n\n".join(
            f"[{rank + 1}] source={self.sources[j]} "
            f"(relevance {fused[j]:.3f}; semantic {semantic[j]:.3f}, keyword {lexical[j]:.3f})\n"
            f"{self.chunks[j]}"
            for rank, j in enumerate(top) if fused[j] >= 0)


STORE = VectorStore()                                      # process-wide singleton
