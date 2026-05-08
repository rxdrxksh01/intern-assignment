"""Duplicate-content detection for cleaned Netflix titles."""

from __future__ import annotations

from typing import Any

from ingestion.models import CleanTitle, IngestStats


def content_key(title: CleanTitle) -> tuple[Any, ...]:
    """Return all title content except show_id for duplicate comparison."""
    return (
        title.title_type,
        title.title,
        title.release_year,
        title.rating,
        title.duration_value,
        title.duration_unit,
        title.date_added,
        title.description,
        tuple(title.countries),
        tuple(title.genres),
        tuple(title.cast_members),
        tuple(title.directors),
    )


def drop_duplicate_content(
    titles: list[CleanTitle],
    stats: IngestStats,
) -> list[CleanTitle]:
    """Drop rows whose cleaned content matches a previous row except show_id."""
    seen: set[tuple[Any, ...]] = set()
    unique_titles: list[CleanTitle] = []

    for title in titles:
        key = content_key(title)

        if key in seen:
            stats.rows_dropped += 1
            stats.dropped_reasons["duplicate_content_except_show_id"] += 1
            continue

        seen.add(key)
        unique_titles.append(title)

    return unique_titles
