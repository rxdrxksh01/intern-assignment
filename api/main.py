"""FastAPI application entrypoint for the Netflix catalogue API."""

from __future__ import annotations

from fastapi import FastAPI

from api.titles import router as titles_router

app = FastAPI(
    title="Netflix Catalog Q&A System",
    description="Structured search API for the cleaned Netflix catalogue.",
    version="0.1.0",
)

app.include_router(titles_router)


@app.get("/health")
def health_check() -> dict[str, str]:
    """Return a basic health check response."""
    return {"status": "ok"}
