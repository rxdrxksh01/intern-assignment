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


def test_titles_filter_by_country_and_type() -> None:
    """Filtering by country and type should return matching titles only."""
    response = client.get("/titles?country=India&type=Movie&page=1&page_size=5")

    assert response.status_code == 200

    body = response.json()
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


def test_ask_returns_answer_and_sources(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ask endpoint should return an answer and at least one source."""
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

    body = response.json()
    assert body["answer"]
    assert len(body["sources"]) >= 1
    assert body["sources"][0]["show_id"] == "81075235"
    assert body["sources"][0]["title"] == "Sarkar"
