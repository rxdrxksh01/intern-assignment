from __future__ import annotations

import csv
import sqlite3
from pathlib import Path

from ingestion.cleaning import clean_row, split_list
from ingestion.models import EXPECTED_COLUMNS, IngestStats
from ingestion.pipeline import load_clean_titles, run_ingestion


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


def test_split_list_removes_empty_and_duplicate_items() -> None:
    """List cleaning should remove blanks and repeated values."""
    stats = IngestStats()

    values = split_list(
        "India, United States, India, ",
        field_name="country",
        stats=stats,
    )

    assert values == ["India", "United States"]
    assert stats.fixes["removed_empty_country_items"] == 1
    assert stats.fixes["removed_duplicate_country_items"] == 1


def test_clean_row_parses_date_duration_and_rating() -> None:
    """A valid row should be cleaned into the expected structured fields."""
    stats = IngestStats()

    cleaned = clean_row(minimal_row(), stats)

    assert cleaned is not None
    assert cleaned.date_added == "2019-09-09"
    assert cleaned.duration_value == 90
    assert cleaned.duration_unit == "minutes"
    assert cleaned.rating == "Not Rated"


def test_clean_row_uses_unknown_for_missing_optional_metadata() -> None:
    """Missing display metadata should become Unknown instead of dropping the row."""
    stats = IngestStats()

    cleaned = clean_row(
        minimal_row(director="", cast="", country="", rating=""),
        stats,
    )

    assert cleaned is not None
    assert cleaned.directors == ["Unknown"]
    assert cleaned.cast_members == ["Unknown"]
    assert cleaned.countries == ["Unknown"]
    assert cleaned.rating == "Unknown"


def test_clean_row_drops_missing_required_title() -> None:
    """Rows without a title should be treated as unusable."""
    stats = IngestStats()

    cleaned = clean_row(minimal_row(title=""), stats)

    assert cleaned is None
    assert stats.rows_dropped == 1
    assert stats.dropped_reasons["missing_or_invalid_title"] == 1


def test_load_clean_titles_drops_duplicate_show_id(tmp_path: Path) -> None:
    """Rows with duplicate show_id should keep only the first row."""
    csv_path = tmp_path / "duplicate_show_id.csv"

    write_csv(
        csv_path,
        [
            minimal_row(show_id="s1", title="First"),
            minimal_row(show_id="s1", title="Second"),
        ],
    )

    titles, stats = load_clean_titles(csv_path)

    assert len(titles) == 1
    assert titles[0].title == "First"
    assert stats.rows_read == 2
    assert stats.rows_dropped == 1
    assert stats.dropped_reasons["duplicate_show_id"] == 1


def test_load_clean_titles_drops_duplicate_content_except_show_id(
    tmp_path: Path,
) -> None:
    """Rows with identical cleaned content except show_id should be deduplicated."""
    csv_path = tmp_path / "duplicate_content.csv"

    write_csv(
        csv_path,
        [
            minimal_row(show_id="s1", title="Same"),
            minimal_row(show_id="s2", title="Same"),
        ],
    )

    titles, stats = load_clean_titles(csv_path)

    assert [title.show_id for title in titles] == ["s1"]
    assert stats.rows_dropped == 1
    assert stats.dropped_reasons["duplicate_content_except_show_id"] == 1


def test_run_ingestion_writes_sqlite_database(tmp_path: Path) -> None:
    """The full ingestion runner should create a usable SQLite database."""
    csv_path = tmp_path / "netflix_titles.csv"
    db_path = tmp_path / "netflix.db"

    write_csv(csv_path, [minimal_row(show_id="s1")])

    run_ingestion(csv_path=csv_path, db_path=db_path)

    assert db_path.exists()

    with sqlite3.connect(db_path) as connection:
        title_count = connection.execute("SELECT COUNT(*) FROM titles").fetchone()[0]
        country_count = connection.execute(
            "SELECT COUNT(*) FROM title_countries"
        ).fetchone()[0]

    assert title_count == 1
    assert country_count == 1
