"""Groq LLM client for grounded Netflix catalogue answers."""

from __future__ import annotations

import os

from dotenv import load_dotenv
from groq import Groq

from rag.config import GROQ_MODEL
from rag.retriever import RetrievedTitle

SYSTEM_MESSAGE = "You answer only from the provided Netflix catalogue sources."


def build_context(titles: list[RetrievedTitle]) -> str:
    """Format retrieved titles as grounded context for the LLM."""
    blocks = []

    for index, title in enumerate(titles, start=1):
        blocks.append(
            f"Source {index}\n"
            f"show_id: {title.show_id}\n"
            f"title: {title.title}\n"
            f"{title.text}"
        )

    return "\n\n---\n\n".join(blocks)


def build_prompt(question: str, titles: list[RetrievedTitle]) -> str:
    """Build the user prompt for grounded catalogue Q&A."""
    context = build_context(titles)

    return f"""
You are a Netflix catalogue assistant.

Answer the user's question using ONLY the catalogue sources below.
Do not use outside knowledge.
If the sources do not contain enough evidence, say that the provided catalogue does not contain enough information.
Mention the title names you used in the answer.
Keep the answer concise.
Do not invent titles, actors, countries, ratings, or years.

User question:
{question}

Catalogue sources:
{context}
""".strip()


def answer_with_groq(question: str, titles: list[RetrievedTitle]) -> str:
    """Send retrieved titles to Groq and return a grounded answer."""
    load_dotenv()

    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is not set. Add it to your .env file.")

    client = Groq(api_key=api_key)

    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_MESSAGE},
            {"role": "user", "content": build_prompt(question, titles)},
        ],
        temperature=0.2,
        max_completion_tokens=500,
    )

    content = response.choices[0].message.content

    if content is None:
        raise RuntimeError("Groq returned an empty response.")

    return content.strip()
