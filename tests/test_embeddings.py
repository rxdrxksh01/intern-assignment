"""Unit tests for the embedding utility functions."""

from __future__ import annotations

import math

import pytest

from rag.embeddings import (
    _extract_single_embedding,
    _validate_embedding,
    normalize_embedding,
)


def test_normalize_embedding_produces_unit_length() -> None:
    """A normalized vector should have magnitude 1.0."""
    vector = [3.0, 4.0]
    result = normalize_embedding(vector)

    magnitude = math.sqrt(sum(x * x for x in result))
    assert abs(magnitude - 1.0) < 1e-6


def test_normalize_embedding_zero_vector_unchanged() -> None:
    """A zero vector should be returned unchanged."""
    vector = [0.0, 0.0, 0.0]
    result = normalize_embedding(vector)

    assert result == [0.0, 0.0, 0.0]


def test_extract_flat_vector() -> None:
    """A flat list like [0.1, 0.2, 0.3] should be returned directly."""
    raw = [0.1, 0.2, 0.3]
    result = _extract_single_embedding(raw)

    assert result == [0.1, 0.2, 0.3]


def test_extract_wrapped_vector() -> None:
    """A wrapped list like [[0.1, 0.2, 0.3]] should be unwrapped."""
    raw = [[0.1, 0.2, 0.3]]
    result = _extract_single_embedding(raw)

    assert result == [0.1, 0.2, 0.3]


def test_extract_token_embeddings_mean_pooled() -> None:
    """Per-token embeddings should be mean-pooled into one vector."""
    raw = [
        [2.0, 4.0],
        [4.0, 6.0],
    ]
    result = _extract_single_embedding(raw)

    assert result == [3.0, 5.0]


def test_extract_empty_raises_error() -> None:
    """An empty embedding should raise a clear error."""
    with pytest.raises(RuntimeError, match="empty embedding"):
        _extract_single_embedding([])


def test_validate_embedding_rejects_empty() -> None:
    """An empty vector should be rejected."""
    with pytest.raises(RuntimeError, match="Empty embedding"):
        _validate_embedding([], context="test")


def test_validate_embedding_accepts_valid() -> None:
    """A non-empty vector should pass validation."""
    _validate_embedding([0.1, 0.2], context="test")
