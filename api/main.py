"""FastAPI application entrypoint for the Netflix catalogue API."""

from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.ask import router as ask_router
from api.titles import router as titles_router

DEFAULT_CORS_ORIGINS = "*"


def get_cors_origins() -> list[str]:
    """Return allowed frontend origins for browser-based API calls."""
    origins = os.environ.get("CORS_ORIGINS", DEFAULT_CORS_ORIGINS)

    if origins == "*":
        return ["*"]

    return [origin.strip() for origin in origins.split(",") if origin.strip()]


app = FastAPI(
    title="Netflix Catalog Q&A System",
    description="Structured search and RAG Q&A API for the cleaned Netflix catalogue.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(titles_router)
app.include_router(ask_router)


@app.get("/health")
def health_check() -> dict[str, str]:
    """Return a basic health check response."""
    return {"status": "ok"}
