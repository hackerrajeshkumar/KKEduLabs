"""Hybrid vector store backed by LanceDB + the process-wide STORE singleton.

The class stays whole: the index writer (``add``) and reader (``search``) live
together so the row-alignment invariant between chunks/tokens/df is
visible in one place. Stateless math is delegated to ``indexing``; the overview
string to ``overview``. Embeddings use the shared Ollama ``client``.
"""
from __future__ import annotations
from collections import Counter
from pathlib import Path
import lancedb
from ..core.config import EMBED_BATCH, DOC_PREFIX, QUERY_PREFIX, TOP_K, LEXICAL_WEIGHT
from ..core import settings
from ..llm.factory import client
from .indexing import parse_records, chunk, tokenize, bm25_scores, min_max_norm
from .overview import build_overview
from .manage import list_documents, remove_document

# Persistent LanceDB store directory (next to the SQLite databases).
_LANCE_DIR = str(Path("lancedb_store").resolve())


class VectorStore:
    """Cosine-similarity + BM25 hybrid search over Ollama embeddings (LanceDB)."""

    def __init__(self) -> None:
        self.chunks: list[str] = []
        self.sources: list[str] = []
        self.chunk_origin: list[str] = []    # bare source filename per chunk (for removal)
        self.titles: list[str] = []          # one per record, for corpus overview
        self.type_labels: list[str] = []     # parallel to titles: each record's stated kind
        self.title_origin: list[str] = []    # parallel to titles: which file each came from
        self.tokens: list[Counter] = []      # per-chunk term frequencies (lexical)
        self.df: Counter = Counter()         # document frequency per term (for idf)

        # LanceDB vector database
        self._db = lancedb.connect(_LANCE_DIR)
        try:
            self._db.drop_table("chunks")    # clean slate on startup (docs restored from rag.db)
        except Exception:
            pass
        self._table = None

    # ------------------------------------------------------------------
    # Embedding helper
    # ------------------------------------------------------------------
    async def _embed(self, texts: list[str], prefix: str = "") -> list[list[float]]:
        """Embed a batch of texts via Ollama. Returns raw embedding vectors;
        LanceDB handles cosine normalization internally."""
        vecs: list[list[float]] = []
        model = settings.get()["embed_model"]
        for i in range(0, len(texts), EMBED_BATCH):        # batch large inputs
            batch = [prefix + t for t in texts[i:i + EMBED_BATCH]]
            resp = await client().embeddings.create(model=model, input=batch)
            vecs += [d.embedding for d in resp.data]
        return vecs

    # ------------------------------------------------------------------
    # Indexing
    # ------------------------------------------------------------------
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

        # Build LanceDB records
        records = [
            {"vector": v, "chunk": c, "source": s, "chunk_origin": source}
            for v, c, s in zip(vecs, new, srcs)
        ]

        if self._table is None:
            self._table = self._db.create_table("chunks", data=records)
        else:
            self._table.add(records)

        self.chunks += new
        self.sources += srcs
        self.chunk_origin += [source] * len(new)
        for c in new:                                  # build lexical index per chunk
            tf = Counter(tokenize(c))
            self.tokens.append(tf)
            self.df.update(tf.keys())                  # one count per distinct term
        return len(new)

    # ------------------------------------------------------------------
    # Document management
    # ------------------------------------------------------------------
    def documents(self) -> list[dict]:
        """One entry per indexed file: name, record count, chunk count."""
        return list_documents(self)

    def remove(self, source: str) -> bool:
        """Drop every chunk/title belonging to one source file."""
        return remove_document(self, source)

    def overview(self) -> str:
        """Corpus-level facts for aggregate/counting/listing questions."""
        return build_overview(self.titles, self.type_labels, self.chunks)

    # ------------------------------------------------------------------
    # Hybrid retrieval
    # ------------------------------------------------------------------
    async def search(self, query: str, k: int = TOP_K,
                     sources: list[str] | None = None) -> str:
        if self._table is None:
            return "No documents are indexed."
        try:
            row_count = self._table.count_rows()
        except Exception:
            return "No documents are indexed."
        if row_count == 0:
            return "No documents are indexed."

        q_vec = (await self._embed([query], QUERY_PREFIX))[0]

        # Retrieve top candidates from LanceDB via cosine similarity
        n_candidates = min(1000, row_count)
        results = self._table.search(q_vec).metric("cosine").limit(n_candidates).to_list()

        # Compute BM25 scores for all indexed chunks
        lexical_all = bm25_scores(query, len(self.chunks), self.tokens, self.df)

        # Map each LanceDB result to its fused score
        semantic_vals: list[float] = []
        lexical_vals: list[float] = []
        result_chunks: list[str] = []
        result_sources: list[str] = []
        result_origins: list[str] = []

        for r in results:
            sem = 1.0 - r["_distance"]               # cosine distance -> similarity
            chunk_text = r["chunk"]
            src = r["source"]
            origin = r["chunk_origin"]

            # Look up the BM25 score for this candidate in the parallel lists
            bm25 = 0.0
            for i, (c, s) in enumerate(zip(self.chunks, self.sources)):
                if c == chunk_text and s == src:
                    bm25 = float(lexical_all[i])
                    break

            semantic_vals.append(sem)
            lexical_vals.append(bm25)
            result_chunks.append(chunk_text)
            result_sources.append(src)
            result_origins.append(origin)

        if not semantic_vals:
            return "No matching documents found."

        # Normalize and fuse both signals to [0,1]
        sem_norm = min_max_norm(semantic_vals)
        lex_norm = min_max_norm(lexical_vals)
        fused = [
            (1 - LEXICAL_WEIGHT) * s + LEXICAL_WEIGHT * l
            for s, l in zip(sem_norm, lex_norm)
        ]

        if sources:                                        # scope to selected files only
            allowed = set(sources)
            fused = [
                f if result_origins[i] in allowed else -1.0
                for i, f in enumerate(fused)
            ]

        # Sort by fused score descending, take top k
        ranked = sorted(range(len(fused)), key=lambda i: fused[i], reverse=True)[:k]

        return "\n\n".join(
            f"[{rank + 1}] source={result_sources[j]} "
            f"(relevance {fused[j]:.3f}; semantic {semantic_vals[j]:.3f}, keyword {lexical_vals[j]:.3f})\n"
            f"{result_chunks[j]}"
            for rank, j in enumerate(ranked) if fused[j] >= 0)


STORE = VectorStore()                                      # process-wide singleton
