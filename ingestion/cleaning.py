"""Cleaning helpers for raw Netflix CSV rows."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from ingestion.models import CleanTitle, IngestStats, UNKNOWN_VALUE, VALID_TYPES

DATE_FORMAT = "%B %d, %Y"
DURATION_RE = re.compile(r"^(?P<value>\d+)\s+(?P<unit>min|Season|Seasons)$")
RATING_REPLACEMENTS = {
    "NR": "Not Rated",
    "UR": "Unrated",
}



def clean_text(value: Any, *, field_name: str, stats: IngestStats) -> str | None:
    """Return a cleaned string, or None for missing/blank values."""
    if value is None:
        stats.missing_values[field_name] += 1
        return None

    raw = str(value)
    cleaned = raw.replace("\xa0", " ")
    cleaned = cleaned.replace("\n", " ").replace("\r", " ").replace("\t", " ")
    cleaned = " ".join(cleaned.split())

    if raw != cleaned:
        stats.fixes[f"cleaned_{field_name}"] += 1

    if cleaned == "":
        stats.missing_values[field_name] += 1
        return None

    return cleaned


def clean_metadata(value: Any, *, field_name: str, stats: IngestStats) -> str:
    """Clean optional display metadata and use Unknown when it is missing."""
    cleaned = clean_text(value, field_name=field_name, stats=stats)

    if cleaned is None:
        return UNKNOWN_VALUE

    return cleaned

def dedupe_preserve_order(values: list[str]) -> list[str]:
    """Remove duplicate list values while keeping the CSV order."""
    seen: set[str] = set()
    deduped: list[str] = []

    for value in values:
        key = value.casefold()

        if key in seen:
            continue

        seen.add(key)
        deduped.append(value)

    return deduped

def split_list(value: str, *, field_name: str, stats: IngestStats) -> list[str]:
    """Split a comma-separated metadata field into ordered unique values."""
    if value == UNKNOWN_VALUE:
        return [UNKNOWN_VALUE]

    parts = [part.strip() for part in value.split(",")]
    values = [part for part in parts if part]

    empty_count = len(parts) - len(values)
    if empty_count:
        stats.fixes[f"removed_empty_{field_name}_items"] += empty_count

    deduped_values = dedupe_preserve_order(values)

    removed_duplicate_count = len(values) - len(deduped_values)
    if removed_duplicate_count:
        stats.fixes[f"removed_duplicate_{field_name}_items"] += removed_duplicate_count

    return deduped_values or [UNKNOWN_VALUE]



def normalize_type(value: Any, stats: IngestStats) -> str | None:
    """Normalize the title type to Movie or TV Show."""
    cleaned = clean_text(value, field_name="type", stats=stats)

    if cleaned is None:
        return None

    normalized = cleaned.title().replace("Tv Show", "TV Show")

    if normalized not in VALID_TYPES:
        stats.anomalies["invalid_type"] += 1
        return None

    return normalized

def normalize_rating(value: Any, stats: IngestStats) -> str:
    """Clean rating and expand unclear rating abbreviations."""
    rating = clean_metadata(value, field_name="rating", stats=stats)
    normalized_rating = RATING_REPLACEMENTS.get(rating, rating)

    if normalized_rating != rating:
        stats.fixes["normalized_rating"] += 1

    return normalized_rating

def parse_release_year(value: Any, stats: IngestStats) -> int | None:
    """Parse release_year as an integer."""
    cleaned = clean_text(value, field_name="release_year", stats=stats)

    if cleaned is None:
        return None

    try:
        return int(cleaned)
    except ValueError:
        stats.anomalies["invalid_release_year"] += 1
        return None


def parse_date_added(value: Any, stats: IngestStats) -> str | None:
    """Parse date_added into YYYY-MM-DD, leaving missing dates as None."""
    cleaned = clean_text(value, field_name="date_added", stats=stats)

    if cleaned is None:
        return None

    try:
        return datetime.strptime(cleaned, DATE_FORMAT).date().isoformat()
    except ValueError:
        stats.anomalies["invalid_date_added"] += 1
        return None


def parse_duration(value: Any, stats: IngestStats) -> tuple[int | None, str | None]:
    """Parse duration into a numeric value and normalized unit."""
    cleaned = clean_text(value, field_name="duration", stats=stats)

    if cleaned is None:
        return None, None

    match = DURATION_RE.match(cleaned)

    if match is None:
        stats.anomalies["invalid_duration"] += 1
        return None, None

    raw_unit = match.group("unit")
    unit = "minutes" if raw_unit == "min" else "seasons"

    return int(match.group("value")), unit


def clean_row(row: dict[str, str], stats: IngestStats) -> CleanTitle | None:
    """Clean one raw CSV row and return None when the row is unusable."""
    show_id = clean_text(row.get("show_id"), field_name="show_id", stats=stats)
    title_type = normalize_type(row.get("type"), stats)
    title = clean_text(row.get("title"), field_name="title", stats=stats)
    release_year = parse_release_year(row.get("release_year"), stats)
    description = clean_text(row.get("description"), field_name="description", stats=stats)

    missing_required = {
        "show_id": show_id,
        "type": title_type,
        "title": title,
        "release_year": release_year,
        "description": description,
    }

    for field_name, cleaned_value in missing_required.items():
        if cleaned_value is None:
            stats.rows_dropped += 1
            stats.dropped_reasons[f"missing_or_invalid_{field_name}"] += 1
            return None

    director_text = clean_metadata(row.get("director"), field_name="director", stats=stats)
    cast_text = clean_metadata(row.get("cast"), field_name="cast", stats=stats)
    country_text = clean_metadata(row.get("country"), field_name="country", stats=stats)
    rating = normalize_rating(row.get("rating"), stats)
    genre_text = clean_metadata(row.get("listed_in"), field_name="listed_in", stats=stats)

    date_added = parse_date_added(row.get("date_added"), stats)
    duration_value, duration_unit = parse_duration(row.get("duration"), stats)

    return CleanTitle(
        show_id=show_id,
        title_type=title_type,
        title=title,
        release_year=release_year,
        rating=rating,
        duration_value=duration_value,
        duration_unit=duration_unit,
        date_added=date_added,
        description=description,
        countries=split_list(country_text, field_name="country", stats=stats),
        genres=split_list(genre_text, field_name="listed_in", stats=stats),
        cast_members=split_list(cast_text, field_name="cast", stats=stats),
        directors=split_list(director_text, field_name="director", stats=stats),
    )
