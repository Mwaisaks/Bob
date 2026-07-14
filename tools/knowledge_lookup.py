"""
knowledge_lookup.py — offline semantic search over the knowledge corpus.

Architecture:
- Chunks each markdown file into paragraphs
- Embeds all chunks using nomic-embed-text (local, CPU-fast)
- Caches embeddings to data/knowledge_embeddings.pkl on first run
- On subsequent runs, loads from cache (near-instant)
- Query: embed the question, return the top-k most similar chunks

Uses cosine similarity over numpy arrays — no external vector DB needed.
"""

import json
import pickle
import re
import sys
from pathlib import Path
from typing import Optional

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

KNOWLEDGE_DIR = Path(__file__).parent.parent / "knowledge"
CACHE_PATH = Path(__file__).parent.parent / "data" / "knowledge_embeddings.pkl"
EMBED_MODEL = "nomic-embed-text"

# Minimum characters for a chunk to be worth embedding
MIN_CHUNK_LEN = 80


def _split_chunks(text: str, source: str) -> list[dict]:
    """
    Split a markdown document into paragraph-level chunks.
    Strips headers but keeps the content under them together.
    """
    chunks = []
    # Split on double newlines (paragraph breaks)
    paragraphs = re.split(r"\n{2,}", text.strip())

    for para in paragraphs:
        para = para.strip()
        if len(para) < MIN_CHUNK_LEN:
            continue
        # Remove markdown table formatting noise but keep the content
        cleaned = re.sub(r"\|[-:]+\|", "", para)
        cleaned = re.sub(r"^\|", "", cleaned, flags=re.MULTILINE)
        cleaned = cleaned.strip()
        if cleaned:
            chunks.append({"text": cleaned, "source": source})

    return chunks


def _load_corpus() -> list[dict]:
    """Load and chunk all markdown files from the knowledge directory."""
    chunks = []
    for path in sorted(KNOWLEDGE_DIR.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        chunks.extend(_split_chunks(text, source=path.name))
    return chunks


def _embed(texts: list[str]) -> np.ndarray:
    """Embed a list of strings using nomic-embed-text via Ollama."""
    import ollama

    vectors = []
    for text in texts:
        resp = ollama.embeddings(model=EMBED_MODEL, prompt=text)
        vectors.append(resp["embedding"])
    return np.array(vectors, dtype=np.float32)


def _cosine_similarity(query_vec: np.ndarray, corpus_vecs: np.ndarray) -> np.ndarray:
    query_norm = query_vec / (np.linalg.norm(query_vec) + 1e-10)
    corpus_norms = corpus_vecs / (np.linalg.norm(corpus_vecs, axis=1, keepdims=True) + 1e-10)
    return corpus_norms @ query_norm


def build_index(force: bool = False):
    """
    Embed all knowledge chunks and cache to disk.
    Only re-runs if the cache is missing or force=True.
    """
    if CACHE_PATH.exists() and not force:
        print(f"Knowledge index already exists at {CACHE_PATH}. Use --force to rebuild.")
        return

    print("Loading knowledge corpus...")
    chunks = _load_corpus()
    print(f"  {len(chunks)} chunks from {len(list(KNOWLEDGE_DIR.glob('*.md')))} files")

    print(f"Embedding with {EMBED_MODEL}...")
    texts = [c["text"] for c in chunks]
    vectors = _embed(texts)

    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CACHE_PATH, "wb") as f:
        pickle.dump({"chunks": chunks, "vectors": vectors}, f)

    print(f"Saved knowledge index → {CACHE_PATH}")


class KnowledgeLookup:
    """
    Lightweight semantic retrieval over the knowledge corpus.
    Loads the cached embedding index on first use.
    """

    def __init__(self):
        self._chunks: Optional[list[dict]] = None
        self._vectors: Optional[np.ndarray] = None

    def _ensure_loaded(self):
        if self._chunks is not None:
            return

        if not CACHE_PATH.exists():
            raise RuntimeError(
                "Knowledge index not built. Run: python tools/knowledge_lookup.py --build"
            )

        with open(CACHE_PATH, "rb") as f:
            data = pickle.load(f)

        self._chunks = data["chunks"]
        self._vectors = data["vectors"]

    def search(self, query: str, top_k: int = 3) -> list[dict]:
        """
        Return the top_k most relevant knowledge chunks for the query.
        Each result has: text, source, score.
        """
        import ollama

        self._ensure_loaded()

        resp = ollama.embeddings(model=EMBED_MODEL, prompt=query)
        query_vec = np.array(resp["embedding"], dtype=np.float32)

        scores = _cosine_similarity(query_vec, self._vectors)
        top_indices = np.argsort(scores)[::-1][:top_k]

        return [
            {
                "text": self._chunks[i]["text"],
                "source": self._chunks[i]["source"],
                "score": float(scores[i]),
            }
            for i in top_indices
        ]


# ---------------------------------------------------------------------------
# Ollama tool schema for the agent loop
# ---------------------------------------------------------------------------

KNOWLEDGE_TOOL = {
    "type": "function",
    "function": {
        "name": "search_knowledge",
        "description": (
            "Search the local knowledge base for information about Kenyan student finance. "
            "Use this when the user asks about HELB, Fuliza terms, M-Pesa fees, savings products "
            "(Ziidi, M-Shwari, Chumz), or general financial advice. "
            "Do NOT use this for questions about the user's own transaction data — use the ledger tools for those."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The specific question or topic to look up",
                }
            },
            "required": ["query"],
        },
    },
}

# Singleton — shared across the agent loop
_lookup = KnowledgeLookup()


def search_knowledge(query: str, top_k: int = 3) -> dict:
    """
    Tool function called by the agent.
    Returns the top matching knowledge chunks with their source files.
    """
    try:
        results = _lookup.search(query, top_k=top_k)
        return {
            "query": query,
            "results": results,
            "note": "Cite the source file when using this information in your answer.",
        }
    except RuntimeError as e:
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# CLI: build the index
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Build or query the knowledge index")
    parser.add_argument("--build", action="store_true", help="Build/rebuild the embedding index")
    parser.add_argument("--force", action="store_true", help="Force rebuild even if index exists")
    parser.add_argument("--query", type=str, help="Test a query against the index")
    parser.add_argument("--top-k", type=int, default=3, help="Number of results to return")
    args = parser.parse_args()

    if args.build or args.force:
        build_index(force=args.force)

    if args.query:
        results = search_knowledge(args.query, top_k=args.top_k)
        print(json.dumps(results, indent=2, ensure_ascii=False))
