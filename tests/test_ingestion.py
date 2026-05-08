from __future__ import annotations

import csv
from pathlib import Path

import pytest

from ingestion.cleaning import clean_row, split_list
from ingestion.models import IngestStats
from ingestion.pipeline import load_clean_titles, run_ingestion


def write_csv(path: Path, *, header: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=header)
        writer.writeheader()
        writer.writerows(rows)


def minimal_row(**overrides: str) -> dict[str, str]:
    base = {
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
    base.update(overrides)
    return base


def test_split_list_removes_empty_items_and_dedupes_preserving_order() -> None:
    stats = IngestStats()
    values = split_list(
        "India, United States, India, ", field_name="country", stats=stats
    )
    assert values == ["India", "United States"]
    assert stats.fixes["removed_empty_country_items"] == 1
    assert stats.fixes["removed_duplicate_country_items"] == 1


def test_clean_row_drops_missing_required_title() -> None:
    stats = IngestStats()
    row = minimal_row(title="")
    cleaned = clean_row(row, stats)
    assert cleaned is None
    assert stats.rows_dropped == 1
    assert stats.dropped_reasons["missing_or_invalid_title"] == 1


def test_load_clean_titles_drops_duplicate_show_id() -> None:
    csv_path = Path("data/_test_dupe_show_id.csv")
    header = list(minimal_row().keys())
    write_csv(
        csv_path,
        header=header,
        rows=[
            minimal_row(show_id="s1", title="A"),
            minimal_row(show_id="s1", title="B"),
        ],
    )

    titles, stats = load_clean_titles(csv_path)
    assert len(titles) == 1
    assert stats.rows_read == 2
    assert stats.rows_dropped == 1
    assert stats.dropped_reasons["duplicate_show_id"] == 1


def test_load_clean_titles_drops_duplicate_content_except_show_id() -> None:
    csv_path = Path("data/_test_dupe_content.csv")
    header = list(minimal_row().keys())
    write_csv(
        csv_path,
        header=header,
        rows=[
            minimal_row(show_id="s1", title="Same"),
            minimal_row(show_id="s2", title="Same"),
        ],
    )

    titles, stats = load_clean_titles(csv_path)
    assert [title.show_id for title in titles] == ["s1"]
    assert stats.rows_dropped == 1
    assert stats.dropped_reasons["duplicate_content_except_show_id"] == 1


def test_run_ingestion_writes_sqlite_db(tmp_path: Path) -> None:
    csv_path = tmp_path / "netflix_titles.csv"
    db_path = tmp_path / "netflix.db"
    header = list(minimal_row().keys())
    write_csv(csv_path, header=header, rows=[minimal_row(show_id="s1")])

    run_ingestion(csv_path=csv_path, db_path=db_path)
    assert db_path.exists()
    assert db_path.stat().st_size > 0


@pytest.fixture(autouse=True)
def cleanup_test_csv_files() -> None:
    # Tests write small CSVs under data/ to exercise the default open() path logic
    # (Path("data/...")). Keep the workspace clean.
    yield
    for name in ("data/_test_dupe_show_id.csv", "data/_test_dupe_content.csv"):
        Path(name).unlink(missing_ok=True)
