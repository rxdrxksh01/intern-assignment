"""Export the cleaned SQLite catalogue to an Excel workbook for inspection."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

DB_PATH = Path("data/netflix.db")
OUTPUT_PATH = Path("data/netflix_cleaned_preview.xlsx")


def read_table(connection: sqlite3.Connection, table_name: str) -> pd.DataFrame:
    """Read a SQLite table into a dataframe."""
    return pd.read_sql_query(f"SELECT * FROM {table_name}", connection)


def export_excel() -> None:
    """Write cleaned catalogue tables to a multi-sheet Excel workbook."""
    if not DB_PATH.exists():
        raise FileNotFoundError("Run `python ingest.py` before exporting Excel.")

    with sqlite3.connect(DB_PATH) as connection:
        titles = read_table(connection, "titles")
        countries = read_table(connection, "title_countries")
        genres = read_table(connection, "title_genres")
        cast = read_table(connection, "title_cast")
        directors = read_table(connection, "title_directors")

        top_countries = pd.read_sql_query(
            """
            SELECT country, COUNT(*) AS title_count
            FROM title_countries
            GROUP BY country
            ORDER BY title_count DESC
            LIMIT 20
            """,
            connection,
        )

    with pd.ExcelWriter(OUTPUT_PATH, engine="openpyxl") as writer:
        titles.to_excel(writer, sheet_name="titles", index=False)
        countries.to_excel(writer, sheet_name="countries", index=False)
        genres.to_excel(writer, sheet_name="genres", index=False)
        cast.to_excel(writer, sheet_name="cast", index=False)
        directors.to_excel(writer, sheet_name="directors", index=False)
        top_countries.to_excel(writer, sheet_name="top_countries", index=False)

    print(f"Excel preview written: {OUTPUT_PATH}")


if __name__ == "__main__":
    export_excel()