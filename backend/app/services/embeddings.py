"""Local embedding service using sentence-transformers."""
from sentence_transformers import SentenceTransformer
from typing import List, Optional
import os
import threading

# ── Model loaded lazily, on first embed ──
# Loading at import cost ~90MB of HuggingFace download before the app could
# start, so the server could not boot without network access to huggingface.co
# and any tooling that merely imported the app paid for it too.
os.environ.setdefault("HF_HUB_DOWNLOAD_TIMEOUT", "300")

_model: Optional[SentenceTransformer] = None
_model_lock = threading.Lock()


def get_model() -> SentenceTransformer:
    """Return the shared model, loading it on first use.

    Locked because uvicorn runs sync endpoints in a threadpool: two concurrent
    first-requests would otherwise each build a model, briefly doubling memory.
    """
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:  # re-check: another thread may have won the race
                print("[embeddings] Loading model...")
                _model = SentenceTransformer("all-MiniLM-L6-v2")
                print("[embeddings] ✅ Model ready.")
    return _model


def embed_text(text: str) -> List[float]:
    """Embed a single text string into a 384-dim vector."""
    embedding = get_model().encode(text, convert_to_numpy=True)
    return embedding.tolist()


def embed_texts(texts: List[str]) -> List[List[float]]:
    """Embed multiple texts in one batch call."""
    embeddings = get_model().encode(texts, convert_to_numpy=True)
    return [emb.tolist() for emb in embeddings]
