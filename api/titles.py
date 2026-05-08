"""FastAPI routes for Netflix catalogue titles and stats."""

from __future__ import annotations

import sqlite3
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from api.database import connect_database
from api.schemas import CountryCount, PaginatedTitlesResponse, StatsResponse, TitleResponse
from ingestion.models import VALID_TYPES

router = APIRouter()

CHILD_TABLES = {
    "countries": ("title_countries", "country"),
    "genres": ("title_genres", "genre"),
    "cast": ("title_cast", "actor_name"),
    "directors": ("title_directors", "director_name"),
}


def open_connection() -> sqlite3.Connection:
    """Open the SQLite database or return a clear API error."""
    try:
        return connect_database()
    except FileNotFoundError as error:
        raise HTTPException(status_code=500, detail=str(error)) from error


def clean_filter_value(value: str | None) -> str | None:
    """Trim optional query filter values."""
    if value is None:
        return None

    cleaned = value.strip()

    return cleaned or None


def validate_type_filter(type_filter: str | None) -> str | None:
    """Validate the optional type query parameter."""
    cleaned = clean_filter_value(type_filter)

    if cleaned is None:
        return None

    normalized = cleaned.title().replace("Tv Show", "TV Show")

    if normalized not in VALID_TYPES:
        raise HTTPException(
            status_code=400,
            detail="type must be either 'Movie' or 'TV Show'",
        )

    return normalized


def build_title_filters(
    *,
    country: str | None,
    release_year: int | None,
    title_type: str | None,
    rating: str | None,
) -> tuple[str, list[Any]]:
    """Build SQL WHERE conditions and parameters for title filters."""
    conditions = ["1 = 1"]
    params: list[Any] = []

    country = clean_filter_value(country)
    rating = clean_filter_value(rating)

    if country is not None:
        conditions.append(
            """
            EXISTS (
                SELECT 1
                FROM title_countries country_filter
                WHERE country_filter.show_id = titles.show_id
                  AND LOWER(country_filter.country) = LOWER(?)
            )
            """
        )
        params.append(country)

    if release_year is not None:
        conditions.append("titles.release_year = ?")
        params.append(release_year)

    if title_type is not None:
        conditions.append("titles.type = ?")
        params.append(title_type)

    if rating is not None:
        conditions.append("LOWER(titles.rating) = LOWER(?)")
        params.append(rating)

    return " AND ".join(conditions), params


def fetch_child_values(
    connection: sqlite3.Connection,
    *,
    show_id: str,
    table_name: str,
    value_column: str,
) -> list[str]:
    """Fetch ordered child-table values for a title."""
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


def build_title_response(
    connection: sqlite3.Connection,
    row: sqlite3.Row,
) -> TitleResponse:
    """Build a TitleResponse from a title row and its child-table values."""
    show_id = str(row["show_id"])

    countries = fetch_child_values(
        connection,
        show_id=show_id,
        table_name=CHILD_TABLES["countries"][0],
        value_column=CHILD_TABLES["countries"][1],
    )
    genres = fetch_child_values(
        connection,
        show_id=show_id,
        table_name=CHILD_TABLES["genres"][0],
        value_column=CHILD_TABLES["genres"][1],
    )
    cast = fetch_child_values(
        connection,
        show_id=show_id,
        table_name=CHILD_TABLES["cast"][0],
        value_column=CHILD_TABLES["cast"][1],
    )
    directors = fetch_child_values(
        connection,
        show_id=show_id,
        table_name=CHILD_TABLES["directors"][0],
        value_column=CHILD_TABLES["directors"][1],
    )

    return TitleResponse(
        show_id=show_id,
        type=str(row["type"]),
        title=str(row["title"]),
        release_year=int(row["release_year"]),
        rating=str(row["rating"]),
        duration_value=row["duration_value"],
        duration_unit=row["duration_unit"],
        date_added=row["date_added"],
        description=str(row["description"]),
        countries=countries,
        genres=genres,
        cast=cast,
        directors=directors,
    )


@router.get("/titles", response_model=PaginatedTitlesResponse)
def list_titles(
    country: str | None = None,
    release_year: int | None = None,
    type_filter: str | None = Query(default=None, alias="type"),
    rating: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> PaginatedTitlesResponse:
    """List titles with optional filters and pagination."""
    title_type = validate_type_filter(type_filter)
    where_sql, params = build_title_filters(
        country=country,
        release_year=release_year,
        title_type=title_type,
        rating=rating,
    )
    offset = (page - 1) * page_size

    with open_connection() as connection:
        total = connection.execute(
            f"SELECT COUNT(*) AS count FROM titles WHERE {where_sql}",
            params,
        ).fetchone()["count"]

        rows = connection.execute(
            f"""
            SELECT show_id, type, title, release_year, rating, duration_value,
                   duration_unit, date_added, description
            FROM titles
            WHERE {where_sql}
            ORDER BY title, show_id
            LIMIT ? OFFSET ?
            """,
            [*params, page_size, offset],
        ).fetchall()

        items = [build_title_response(connection, row) for row in rows]

    return PaginatedTitlesResponse(
        items=items,
        page=page,
        page_size=page_size,
        total=int(total),
    )


@router.get("/titles/{show_id}", response_model=TitleResponse)
def get_title(show_id: str) -> TitleResponse:
    """Return one title by show_id."""
    with open_connection() as connection:
        row = connection.execute(
            """
            SELECT show_id, type, title, release_year, rating, duration_value,
                   duration_unit, date_added, description
            FROM titles
            WHERE show_id = ?
            """,
            (show_id,),
        ).fetchone()

        if row is None:
            raise HTTPException(status_code=404, detail="Title not found")

        return build_title_response(connection, row)


@router.get("/stats", response_model=StatsResponse)
def get_stats() -> StatsResponse:
    """Return catalogue-level summary statistics."""
    with open_connection() as connection:
        total_titles = connection.execute(
            "SELECT COUNT(*) AS count FROM titles"
        ).fetchone()["count"]

        type_rows = connection.execute(
            """
            SELECT type, COUNT(*) AS count
            FROM titles
            GROUP BY type
            ORDER BY type
            """
        ).fetchall()

        country_rows = connection.execute(
            """
            SELECT country, COUNT(*) AS count
            FROM title_countries
            GROUP BY country
            ORDER BY count DESC, country
            LIMIT 10
            """
        ).fetchall()

    return StatsResponse(
        total_titles=int(total_titles),
        count_by_type={str(row["type"]): int(row["count"]) for row in type_rows},
        top_countries=[
            CountryCount(country=str(row["country"]), count=int(row["count"]))
            for row in country_rows
        ],
    )
