from __future__ import annotations

import csv
from pathlib import Path

from ingestion.cleaning import clean_row
from ingestion.models import EXPECTED_COLUMNS, IngestStats
from ingestion.pipeline import load_clean_titles


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    """Write a small CSV fixture for ingestion tests."""
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=EXPECTED_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def minimal_row(**overrides: str) -> dict[str, str]:
    """Return a valid minimal Netflix CSV row for tests."""
    row = {
        "show_id": "s1",
        "type": "Movie",
        "title": "Example Title",
        "director": "",
        "cast": "",
        "country": "",
        "date_added": "September 9, 2019",
        "release_year": "2019",
        "rating": "NR",
        "duration": "90 min",
        "listed_in": "Comedies",
        "description": "Some description",
    }
    row.update(overrides)
    return row


def test_ingestion_drops_missing_title(tmp_path: Path) -> None:
    """Rows without a title should be dropped during ingestion."""
    csv_path = tmp_path / "missing_title.csv"

    write_csv(csv_path, [minimal_row(title="")])

    titles, stats = load_clean_titles(csv_path)

    assert titles == []
    assert stats.rows_read == 1
    assert stats.rows_dropped == 1
    assert stats.dropped_reasons["missing_or_invalid_title"] == 1


def test_clean_row_parses_metadata_fields() -> None:
    """A valid row should parse dates, duration, ratings, and missing metadata."""
    stats = IngestStats()

    cleaned = clean_row(minimal_row(), stats)

    assert cleaned is not None
    assert cleaned.date_added == "2019-09-09"
    assert cleaned.duration_value == 90
    assert cleaned.duration_unit == "minutes"
    assert cleaned.rating == "Not Rated"
    assert cleaned.directors == ["Unknown"]
    assert cleaned.cast_members == ["Unknown"]
    assert cleaned.countries == ["Unknown"]


def test_ingestion_drops_duplicate_content_except_show_id(tmp_path: Path) -> None:
    """Rows with identical cleaned content except show_id should be deduplicated."""
    csv_path = tmp_path / "duplicate_content.csv"

    write_csv(
        csv_path,
        [
            minimal_row(show_id="s1", title="Same Title"),
            minimal_row(show_id="s2", title="Same Title"),
        ],
    )

    titles, stats = load_clean_titles(csv_path)

    assert [title.show_id for title in titles] == ["s1"]
    assert stats.rows_read == 2
    assert stats.rows_dropped == 1
    assert stats.dropped_reasons["duplicate_content_except_show_id"] == 1
