"""SQLite schema and insert logic for the cleaned Netflix catalogue."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from ingestion.models import CleanTitle


def create_schema(connection: sqlite3.Connection) -> None:
    """Create all ingestion tables from scratch."""
    connection.executescript(
        """
        DROP TABLE IF EXISTS title_directors;
        DROP TABLE IF EXISTS title_cast;
        DROP TABLE IF EXISTS title_genres;
        DROP TABLE IF EXISTS title_countries;
        DROP TABLE IF EXISTS titles;

        CREATE TABLE titles (
            show_id TEXT PRIMARY KEY,
            type TEXT NOT NULL CHECK (type IN ('Movie', 'TV Show')),
            title TEXT NOT NULL,
            release_year INTEGER NOT NULL,
            rating TEXT NOT NULL,
            duration_value INTEGER,
            duration_unit TEXT CHECK (
                duration_unit IS NULL OR duration_unit IN ('minutes', 'seasons')
            ),
            date_added TEXT,
            description TEXT NOT NULL
        );

        CREATE TABLE title_countries (
            show_id TEXT NOT NULL REFERENCES titles(show_id) ON DELETE CASCADE,
            country TEXT NOT NULL,
            position INTEGER NOT NULL,
            PRIMARY KEY (show_id, position)
        );

        CREATE TABLE title_genres (
            show_id TEXT NOT NULL REFERENCES titles(show_id) ON DELETE CASCADE,
            genre TEXT NOT NULL,
            position INTEGER NOT NULL,
            PRIMARY KEY (show_id, position)
        );

        CREATE TABLE title_cast (
            show_id TEXT NOT NULL REFERENCES titles(show_id) ON DELETE CASCADE,
            actor_name TEXT NOT NULL,
            position INTEGER NOT NULL,
            PRIMARY KEY (show_id, position)
        );

        CREATE TABLE title_directors (
            show_id TEXT NOT NULL REFERENCES titles(show_id) ON DELETE CASCADE,
            director_name TEXT NOT NULL,
            position INTEGER NOT NULL,
            PRIMARY KEY (show_id, position)
        );

        CREATE INDEX idx_titles_type ON titles(type);
        CREATE INDEX idx_titles_release_year ON titles(release_year);
        CREATE INDEX idx_titles_rating ON titles(rating);
        CREATE INDEX idx_title_countries_country ON title_countries(country);
        CREATE INDEX idx_title_genres_genre ON title_genres(genre);
        """
    )


def insert_child_values(
    connection: sqlite3.Connection,
    *,
    table_name: str,
    value_column: str,
    show_id: str,
    values: list[str],
) -> None:
    """Insert ordered values for one child table."""
    rows = [(show_id, value, index) for index, value in enumerate(values, start=1)]

    connection.executemany(
        f"INSERT INTO {table_name} (show_id, {value_column}, position) VALUES (?, ?, ?)",
        rows,
    )


def insert_title(connection: sqlite3.Connection, title: CleanTitle) -> None:
    """Insert one cleaned title and its child-table values."""
    connection.execute(
        """
        INSERT INTO titles (
            show_id,
            type,
            title,
            release_year,
            rating,
            duration_value,
            duration_unit,
            date_added,
            description
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            title.show_id,
            title.title_type,
            title.title,
            title.release_year,
            title.rating,
            title.duration_value,
            title.duration_unit,
            title.date_added,
            title.description,
        ),
    )

    insert_child_values(
        connection,
        table_name="title_countries",
        value_column="country",
        show_id=title.show_id,
        values=title.countries,
    )
    insert_child_values(
        connection,
        table_name="title_genres",
        value_column="genre",
        show_id=title.show_id,
        values=title.genres,
    )
    insert_child_values(
        connection,
        table_name="title_cast",
        value_column="actor_name",
        show_id=title.show_id,
        values=title.cast_members,
    )
    insert_child_values(
        connection,
        table_name="title_directors",
        value_column="director_name",
        show_id=title.show_id,
        values=title.directors,
    )


def write_database(titles: list[CleanTitle], db_path: Path) -> None:
    """Write cleaned titles into a fresh SQLite database."""
    db_path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(db_path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        create_schema(connection)

        for title in titles:
            insert_title(connection, title)

        connection.commit()
