"""Shared embedding utilities using the Hugging Face Inference API."""

from __future__ import annotations

import logging
import math
import time
from typing import Any

from rag.config import EMBEDDING_MODEL_NAME, HF_API_TOKEN

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 2


def _get_hf_client() -> Any:
    """Create a Hugging Face InferenceClient with token validation."""
    if not HF_API_TOKEN:
        raise RuntimeError("HF_API_TOKEN is not set. Add it to your .env file.")

    from huggingface_hub import InferenceClient

    return InferenceClient(token=HF_API_TOKEN)


def normalize_embedding(vector: list[float]) -> list[float]:
    """Normalize a vector to unit length for cosine similarity.

    This matches the behavior of SentenceTransformer's
    normalize_embeddings=True parameter so cosine distance
    calculations in Chroma remain consistent.
    """
    magnitude = math.sqrt(sum(x * x for x in vector))

    if magnitude == 0:
        return vector

    return [x / magnitude for x in vector]


def _to_flat_list(value: Any) -> list[float]:
    """Convert a numpy array or nested list to a flat Python list of floats."""
    if hasattr(value, "tolist"):
        value = value.tolist()

    return [float(x) for x in value]


def _extract_single_embedding(raw: Any) -> list[float]:
    """Extract a single embedding vector from HF API output.

    Hugging Face feature_extraction can return different shapes:
    - [384]               → single vector (sentence-level)
    - [[384]]             → single vector wrapped in a list
    - [[tok1], [tok2], ...] → per-token embeddings (need mean pooling)

    This function handles all cases and always returns a flat list.
    """
    if hasattr(raw, "tolist"):
        raw = raw.tolist()

    if not raw:
        raise RuntimeError("Hugging Face returned an empty embedding.")

    first_element = raw[0]

    if isinstance(first_element, (int, float)):
        return _to_flat_list(raw)

    if isinstance(first_element, list):
        if len(raw) == 1:
            return _to_flat_list(raw[0])

        dimension = len(raw[0])
        pooled = [0.0] * dimension

        for token_vector in raw:
            for i, value in enumerate(token_vector):
                pooled[i] += float(value)

        token_count = len(raw)
        return [value / token_count for value in pooled]

    raise RuntimeError(f"Unexpected embedding format: {type(first_element)}")


def _validate_embedding(vector: list[float], *, context: str) -> None:
    """Raise an error if the embedding is empty or invalid."""
    if not vector:
        raise RuntimeError(f"Empty embedding returned for {context}.")


def _call_hf_api(client: Any, text: str) -> Any:
    """Call the HF feature_extraction API with retry logic."""
    last_error: Exception | None = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return client.feature_extraction(
                text,
                model=EMBEDDING_MODEL_NAME,
            )
        except Exception as error:
            last_error = error
            logger.warning(
                "HF API attempt %d/%d failed: %s", attempt, MAX_RETRIES, error
            )

            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY_SECONDS)

    raise RuntimeError(
        f"Hugging Face API failed after {MAX_RETRIES} attempts: {last_error}"
    )


def embed_one_text(client: Any, text: str) -> list[float]:
    """Embed a single text and return a normalized vector."""
    raw = _call_hf_api(client, text)
    vector = _extract_single_embedding(raw)
    _validate_embedding(vector, context="single text")

    return normalize_embedding(vector)


def embed_texts(client: Any, texts: list[str]) -> list[list[float]]:
    """Embed multiple texts and return normalized vectors.

    Embeds one text at a time for reliability — avoids HF API
    payload size limits and inconsistent batch output shapes.
    """
    embeddings: list[list[float]] = []
    expected_dimension: int | None = None

    for index, text in enumerate(texts):
        vector = embed_one_text(client, text)

        if expected_dimension is None:
            expected_dimension = len(vector)
        elif len(vector) != expected_dimension:
            raise RuntimeError(
                f"Dimension mismatch at index {index}: "
                f"expected {expected_dimension}, got {len(vector)}. "
                f"Rebuild the index with `python -m rag.index`."
            )

        embeddings.append(vector)

    return embeddings
