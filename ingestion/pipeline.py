"""End-to-end ingestion pipeline for the Netflix catalogue."""

from __future__ import annotations

import csv
from pathlib import Path

from ingestion.cleaning import clean_row
from ingestion.database import write_database
from ingestion.duplicates import drop_duplicate_content
from ingestion.models import CSV_PATH, DB_PATH, EXPECTED_COLUMNS, CleanTitle, IngestStats


def validate_columns(columns: list[str] | None) -> None:
    """Fail early if the CSV does not have the expected header."""
    if columns is None:
        raise ValueError("CSV file has no header row.")

    missing_columns = set(EXPECTED_COLUMNS) - set(columns)

    if missing_columns:
        raise ValueError(f"Missing expected columns: {sorted(missing_columns)}")


def load_clean_titles(csv_path: Path) -> tuple[list[CleanTitle], IngestStats]:
    """Load, clean, validate, and deduplicate title rows from the CSV."""
    stats = IngestStats()
    titles: list[CleanTitle] = []
    seen_show_ids: set[str] = set()

    with csv_path.open(newline="", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        validate_columns(reader.fieldnames)

        for row in reader:
            stats.rows_read += 1
            title = clean_row(row, stats)

            if title is None:
                continue

            if title.show_id in seen_show_ids:
                stats.rows_dropped += 1
                stats.dropped_reasons["duplicate_show_id"] += 1
                continue

            seen_show_ids.add(title.show_id)
            titles.append(title)

    titles = drop_duplicate_content(titles, stats)
    stats.rows_loaded = len(titles)

    return titles, stats


def print_summary(stats: IngestStats, db_path: Path) -> None:
    """Print a human-readable ingestion summary."""
    print("Ingestion complete")
    print("------------------")
    print(f"Database written: {db_path}")
    print(f"Rows read:        {stats.rows_read}")
    print(f"Rows loaded:      {stats.rows_loaded}")
    print(f"Rows dropped:     {stats.rows_dropped}")

    if stats.dropped_reasons:
        print("\nDropped rows by reason:")
        for reason, count in stats.dropped_reasons.most_common():
            print(f"  - {reason}: {count}")

    if stats.missing_values:
        print("\nMissing values handled:")
        for field_name, count in stats.missing_values.most_common():
            print(f"  - {field_name}: {count}")

    if stats.fixes:
        print("\nCleaning fixes applied:")
        for fix_name, count in stats.fixes.most_common():
            print(f"  - {fix_name}: {count}")

    if stats.anomalies:
        print("\nAnomalies observed:")
        for anomaly, count in stats.anomalies.most_common():
            print(f"  - {anomaly}: {count}")


def run_ingestion(csv_path: Path = CSV_PATH, db_path: Path = DB_PATH) -> None:
    """Run the full CSV-to-SQLite ingestion flow."""
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    titles, stats = load_clean_titles(csv_path)
    write_database(titles, db_path)
    print_summary(stats, db_path)
