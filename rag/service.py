"""RAG service that retrieves titles and asks Groq for an answer."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from rag.config import RAG_TOP_K
from rag.llm import answer_with_groq
from rag.retriever import RetrievedTitle, TitleRetriever


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


@lru_cache(maxsize=1)
def get_retriever() -> TitleRetriever:
    """Create the retriever once and reuse it across requests."""
    return TitleRetriever()


def select_used_sources(
    retrieved_titles: list[RetrievedTitle],
    used_show_ids: list[str],
) -> list[AnswerSource]:
    """Return only retrieved sources that the LLM said it used."""
    title_by_id = {title.show_id: title for title in retrieved_titles}
    sources = []

    for show_id in used_show_ids:
        title = title_by_id.get(show_id)

        if title is not None:
            sources.append(AnswerSource(show_id=title.show_id, title=title.title))

    return sources


def ask_question(question: str, top_k: int = RAG_TOP_K) -> AskResult:
    """Retrieve relevant titles, ask Groq, and return answer with used sources."""
    retriever = get_retriever()
    retrieved_titles = retriever.retrieve(question, top_k=top_k)

    if not retrieved_titles:
        return AskResult(
            answer="I could not find relevant titles in the provided catalogue.",
            sources=[],
        )

    llm_answer = answer_with_groq(question, retrieved_titles)
    sources = select_used_sources(retrieved_titles, llm_answer.used_show_ids)

    return AskResult(answer=llm_answer.answer, sources=sources)
