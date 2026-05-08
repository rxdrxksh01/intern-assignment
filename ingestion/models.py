"""Shared models and constants for Netflix catalogue ingestion."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

CSV_PATH = Path("data/netflix_titles.csv")
DB_PATH = Path("data/netflix.db")
UNKNOWN_VALUE = "Unknown"
VALID_TYPES = {"Movie", "TV Show"}

EXPECTED_COLUMNS = [
    "show_id",
    "type",
    "title",
    "director",
    "cast",
    "country",
    "date_added",
    "release_year",
    "rating",
    "duration",
    "listed_in",
    "description",
]


@dataclass
class IngestStats:
    """Counts collected during ingestion for the final summary report."""

    rows_read: int = 0
    rows_loaded: int = 0
    rows_dropped: int = 0
    dropped_reasons: Counter[str] = field(default_factory=Counter)
    missing_values: Counter[str] = field(default_factory=Counter)
    fixes: Counter[str] = field(default_factory=Counter)
    anomalies: Counter[str] = field(default_factory=Counter)


@dataclass(frozen=True)
class CleanTitle:
    """Cleaned title data ready to be inserted into SQLite."""

    show_id: str
    title_type: str
    title: str
    release_year: int
    rating: str
    duration_value: int | None
    duration_unit: str | None
    date_added: str | None
    description: str
    countries: list[str]
    genres: list[str]
    cast_members: list[str]
    directors: list[str]
