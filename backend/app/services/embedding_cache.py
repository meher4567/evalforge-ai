"""
Embedding computation and pgvector-based caching.

Uses sentence-transformers (all-MiniLM-L6-v2 by default) for semantic embeddings.
Caches results in the pgvector `embedding_cache` table to avoid recomputation.
"""

from __future__ import annotations

import hashlib
import logging
from functools import lru_cache

from sqlalchemy import text as sql_text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import EvalCase as EvalCaseModel  # noqa: F401 used by string reference

logger = logging.getLogger("evalforge.embedding_cache")

EMBEDDING_MODEL_ID = "all-MiniLM-L6-v2"
EMBEDDING_DIM = 384


@lru_cache(maxsize=1)
def _load_embedding_model():
    """Load the sentence-transformer model once and cache it in-process."""
    # Deferred import so the package is only loaded when actually used
    from sentence_transformers import SentenceTransformer

    logger.info("Loading embedding model: %s", EMBEDDING_MODEL_ID)
    model = SentenceTransformer(EMBEDDING_MODEL_ID)
    logger.info("Embedding model loaded, dim=%d", model.get_sentence_embedding_dimension())
    return model


def _text_hash(text: str) -> str:
    """SHA-256 hex hash of the normalized text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


async def get_or_compute_embedding(
    session: AsyncSession,
    text: str,
) -> list[float]:
    """
    Retrieve a cached embedding for the given text, or compute and cache it.

    Returns a list[float] of length EMBEDDING_DIM (384).
    """
    if not text:
        return [0.0] * EMBEDDING_DIM

    hash_value = _text_hash(text)

    # Check cache in pgvector
    result = await session.execute(
        sql_text(
            "SELECT embedding FROM embedding_cache WHERE text_hash = :hash AND model_id = :model"
        ),
        {"hash": hash_value, "model": EMBEDDING_MODEL_ID},
    )
    row = result.first()
    if row is not None:
        # pgvector stores embeddings as string representation; parse to list
        embedding_str = row[0]
        if embedding_str:
            return _parse_vector(embedding_str)

    # Compute
    model = _load_embedding_model()
    embedding = model.encode(text, normalize_embeddings=True).tolist()

    # Cache
    await session.execute(
        sql_text(
            "INSERT INTO embedding_cache (text_hash, model_id, embedding) "
            "VALUES (:hash, :model, :emb) "
            "ON CONFLICT (text_hash, model_id) DO NOTHING"
        ),
        {
            "hash": hash_value,
            "model": EMBEDDING_MODEL_ID,
            "emb": _format_vector(embedding),
        },
    )
    await session.flush()

    return embedding


def compute_embedding_sync(text: str) -> list[float]:
    """Synchronous embedding computation for worker use."""
    if not text:
        return [0.0] * EMBEDDING_DIM
    model = _load_embedding_model()
    return model.encode(text, normalize_embeddings=True).tolist()


def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """Compute cosine similarity between two embedding vectors (both assumed normalized)."""
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0
    dot = sum(a * b for a, b in zip(vec_a, vec_b, strict=True))
    # Vectors are already normalized, so similarity is just the dot product
    return max(0.0, min(1.0, dot))


def _format_vector(embedding: list[float]) -> str:
    """Format a Python list as a pgvector-compatible string."""
    return "[" + ",".join(str(x) for x in embedding) + "]"


def _parse_vector(vector_str: str) -> list[float]:
    """Parse a pgvector string representation back to a Python list."""
    # pgvector returns e.g. "[0.1,0.2,0.3]"
    stripped = vector_str.strip("[]")
    if not stripped:
        return []
    return [float(x.strip()) for x in stripped.split(",")]
