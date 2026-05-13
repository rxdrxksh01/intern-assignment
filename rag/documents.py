"""Build searchable RAG documents from the cleaned Netflix database."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from api.database import connect_database


@dataclass
class TitleDocument:
    """A catalogue title represented as text plus metadata for retrieval."""

    show_id: str
    title: str
    text: str
    metadata: dict[str, str | int | float | bool | list[str] | None]


def fetch_child_values(
    connection: sqlite3.Connection,
    *,
    table_name: str,
    value_column: str,
    show_id: str,
) -> list[str]:
    """Fetch ordered child-table values for one title."""
    rows = connection.execute(
        f"""
        SELECT {value_column}
        FROM {table_name}
        WHERE show_id = ?
        ORDER BY position
        """,
        (show_id,),
    ).fetchall()

    return [str(row[value_column]) for row in rows]


def build_document_text(
    *,
    row: sqlite3.Row,
    countries: list[str],
    genres: list[str],
    cast: list[str],
    directors: list[str],
) -> str:
    """Build the text that will be embedded for one Netflix title."""
    duration = "Unknown"
    if row["duration_value"] is not None and row["duration_unit"] is not None:
        duration = f"{row['duration_value']} {row['duration_unit']}"

    parts = [
        f"Title: {row['title']}",
        f"Type: {row['type']}",
        f"Release year: {row['release_year']}",
        f"Rating: {row['rating']}",
        f"Duration: {duration}",
        f"Countries: {', '.join(countries)}",
        f"Genres: {', '.join(genres)}",
        f"Directors: {', '.join(directors)}",
        f"Cast: {', '.join(cast)}",
        f"Description: {row['description']}",
    ]

    return "\n".join(parts)

def ensure_non_empty_metadata_list(values: list[str]) -> list[str]:
    """Return a non-empty metadata list for Chroma filters."""
    clean_values = [value.strip() for value in values if value.strip()]
    return clean_values or ["Unknown"]

def load_title_documents() -> list[TitleDocument]:
    """Load all cleaned titles from SQLite and convert them to RAG documents."""
    documents: list[TitleDocument] = []

    with connect_database() as connection:
        rows = connection.execute(
            """
            SELECT show_id, type, title, release_year, rating, duration_value,
                   duration_unit, date_added, description
            FROM titles
            ORDER BY show_id
            """
        ).fetchall()

        for row in rows:
            show_id = str(row["show_id"])
            countries = fetch_child_values(
                connection,
                table_name="title_countries",
                value_column="country",
                show_id=show_id,
            )
            genres = fetch_child_values(
                connection,
                table_name="title_genres",
                value_column="genre",
                show_id=show_id,
            )
            cast = fetch_child_values(
                connection,
                table_name="title_cast",
                value_column="actor_name",
                show_id=show_id,
            )
            directors = fetch_child_values(
                connection,
                table_name="title_directors",
                value_column="director_name",
                show_id=show_id,
            )

            text = build_document_text(
                row=row,
                countries=countries,
                genres=genres,
                cast=cast,
                directors=directors,
            )
            metadata_countries = ensure_non_empty_metadata_list(countries)
            metadata_genres = ensure_non_empty_metadata_list(genres)

            documents.append(
                TitleDocument(
                    show_id=show_id,
                    title=str(row["title"]),
                    text=text,
                    metadata={
                        "show_id": show_id,
                        "title": str(row["title"]),
                        "type": str(row["type"]),
                        "release_year": int(row["release_year"]),
                        "rating": str(row["rating"]),
                        "countries": metadata_countries,
                        "genres": metadata_genres,
                    },
                )
            )

    return documents
