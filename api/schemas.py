"""Response schemas for the Netflix API."""

from __future__ import annotations

from pydantic import BaseModel


class TitleResponse(BaseModel):
    """A Netflix title returned by the API."""

    show_id: str
    type: str
    title: str
    release_year: int
    rating: str
    duration_value: int | None
    duration_unit: str | None
    date_added: str | None
    description: str
    countries: list[str]
    genres: list[str]
    cast: list[str]
    directors: list[str]


class PaginatedTitlesResponse(BaseModel):
    """Paginated list response for /titles."""

    items: list[TitleResponse]
    page: int
    page_size: int
    total: int


class CountryCount(BaseModel):
    """Country count item for stats."""

    country: str
    count: int


class StatsResponse(BaseModel):
    """Summary statistics for the catalogue."""

    total_titles: int
    count_by_type: dict[str, int]
    top_countries: list[CountryCount]


class AskRequest(BaseModel):
    """Request body for the RAG Q&A endpoint."""

    question: str


class AskSource(BaseModel):
    """A source title used by the RAG answer."""

    show_id: str
    title: str


class AskResponse(BaseModel):
    """Response from the RAG Q&A endpoint."""

    answer: str
    sources: list[AskSource]
