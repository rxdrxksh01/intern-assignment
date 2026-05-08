"""FastAPI route for RAG-based Netflix catalogue Q&A."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from api.schemas import AskRequest, AskResponse, AskSource
from rag.service import ask_question

router = APIRouter()


@router.post("/ask", response_model=AskResponse)
def ask_catalogue(request: AskRequest) -> AskResponse:
    """Answer a natural-language question using retrieved catalogue titles."""
    question = request.question.strip()

    if not question:
        raise HTTPException(status_code=400, detail="question must not be empty")

    try:
        result = ask_question(question)
    except FileNotFoundError as error:
        raise HTTPException(status_code=500, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=500, detail=str(error)) from error

    return AskResponse(
        answer=result.answer,
        sources=[
            AskSource(show_id=source.show_id, title=source.title)
            for source in result.sources
        ],
    )
