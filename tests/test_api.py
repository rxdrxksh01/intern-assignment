from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from api.main import app
from ingestion.pipeline import run_ingestion


@pytest.fixture(scope="module", autouse=True)
def build_test_database() -> None:
    """Create the SQLite database used by API tests."""
    run_ingestion()


client = TestClient(app)


def test_health_check_returns_ok() -> None:
    """Health endpoint should confirm the API is running."""
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_titles_filter_by_country_and_type() -> None:
    """Filtering by country and type should return matching titles only."""
    response = client.get("/titles?country=India&type=Movie&page=1&page_size=5")

    assert response.status_code == 200

    body = response.json()
    assert body["page"] == 1
    assert body["page_size"] == 5
    assert body["total"] > 0
    assert len(body["items"]) > 0

    for item in body["items"]:
        assert item["type"] == "Movie"
        assert "India" in item["countries"]


def test_get_title_returns_404_for_missing_show_id() -> None:
    """Unknown show_id should return a clean 404 response."""
    response = client.get("/titles/DOES_NOT_EXIST")

    assert response.status_code == 404
    assert response.json()["detail"] == "Title not found"


def test_stats_returns_expected_structure() -> None:
    """Stats endpoint should return totals, type counts, and top countries."""
    response = client.get("/stats")

    assert response.status_code == 200

    body = response.json()
    assert body["total_titles"] == 6233
    assert "Movie" in body["count_by_type"]
    assert "TV Show" in body["count_by_type"]
    assert len(body["top_countries"]) == 10

    top_country_names = [item["country"] for item in body["top_countries"]]
    assert "United States" in top_country_names
    assert "Unknown" not in top_country_names


def test_ask_rejects_empty_question() -> None:
    """Ask endpoint should reject blank questions before calling RAG."""
    response = client.post("/ask", json={"question": "   "})

    assert response.status_code == 400
    assert response.json()["detail"] == "question must not be empty"


def test_ask_returns_answer_and_sources(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ask endpoint should return the RAG answer and source titles."""
    fake_result = SimpleNamespace(
        answer="Try Sarkar from the catalogue.",
        sources=[
            SimpleNamespace(show_id="81075235", title="Sarkar"),
        ],
    )

    def fake_ask_question(question: str) -> SimpleNamespace:
        assert question == "Suggest an Indian political movie"
        return fake_result

    monkeypatch.setattr("api.ask.ask_question", fake_ask_question)

    response = client.post(
        "/ask",
        json={"question": "Suggest an Indian political movie"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "answer": "Try Sarkar from the catalogue.",
        "sources": [
            {
                "show_id": "81075235",
                "title": "Sarkar",
            }
        ],
    }
