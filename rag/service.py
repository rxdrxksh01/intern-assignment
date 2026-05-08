"""RAG service that retrieves titles and asks Groq for an answer."""

from __future__ import annotations

from dataclasses import dataclass

from rag.config import RAG_TOP_K
from rag.llm import answer_with_groq
from rag.retriever import TitleRetriever


@dataclass
class AnswerSource:
    """A source title used in a RAG answer."""

    show_id: str
    title: str


@dataclass
class AskResult:
    """Final RAG answer plus source titles."""

    answer: str
    sources: list[AnswerSource]


def ask_question(question: str, top_k: int = RAG_TOP_K) -> AskResult:
    """Retrieve relevant titles, ask Groq, and return answer with sources."""
    retriever = TitleRetriever()
    retrieved_titles = retriever.retrieve(question, top_k=top_k)

    if not retrieved_titles:
        return AskResult(
            answer="I could not find relevant titles in the provided catalogue.",
            sources=[],
        )

    answer = answer_with_groq(question, retrieved_titles)

    return AskResult(
        answer=answer,
        sources=[
            AnswerSource(show_id=title.show_id, title=title.title)
            for title in retrieved_titles
        ],
    )
