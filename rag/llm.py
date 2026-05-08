"""Groq LLM client for grounded Netflix catalogue answers."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass

from dotenv import load_dotenv

from rag.config import GROQ_MODEL
from rag.retriever import RetrievedTitle

SYSTEM_MESSAGE = """
You are a Netflix catalogue Q&A assistant.

Rules:
- Use only the provided catalogue sources.
- Do not use outside knowledge.
- Do not invent titles, actors, countries, ratings, years, or plot details.
- If the sources do not support the question, say the catalogue does not contain enough information.
- Only cite show_ids that you actually used in the answer.
- Return valid JSON only. Do not wrap it in markdown.
- For recommendation questions, suggest up to 4 relevant titles when the sources support them.
""".strip()

FEW_SHOT_EXAMPLES = """
Example 1

User question:
Suggest an Indian comedy movie.

Catalogue sources:
Source 1
show_id: 111
title: Example Comedy
Title: Example Comedy
Type: Movie
Countries: India
Genres: Comedies
Description: A light comedy about family confusion.

Source 2
show_id: 222
title: Example Thriller
Title: Example Thriller
Type: Movie
Countries: India
Genres: Thrillers
Description: A dark crime story.

Correct JSON response:
{
  "answer": "A good match is Example Comedy. It is an Indian movie listed under Comedies, so it fits your request.",
  "used_show_ids": ["111"]
}

Example 2

User question:
Which catalogue titles are about space travel?

Catalogue sources:
Source 1
show_id: 333
title: Ocean Story
Title: Ocean Story
Type: Movie
Countries: United States
Genres: Documentaries
Description: A documentary about marine life.

Correct JSON response:
{
  "answer": "The provided catalogue sources do not contain enough information to recommend a title about space travel.",
  "used_show_ids": []
}
""".strip()


@dataclass
class LLMAnswer:
    """Parsed LLM answer with the source ids it used."""

    answer: str
    used_show_ids: list[str]


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
    """Build a guarded few-shot prompt for grounded catalogue Q&A."""
    context = build_context(titles)

    return f"""
{FEW_SHOT_EXAMPLES}

Now answer the actual user question.

User question:
{question}

Catalogue sources:
{context}

Return JSON with exactly these keys:
- "answer": string
- "used_show_ids": list of strings

Important:
- The answer must be based only on the catalogue sources above.
- "used_show_ids" must include only show_ids that directly support the answer.
- If none of the sources support the question, use an empty list for "used_show_ids".
""".strip()


def parse_llm_json(content: str) -> LLMAnswer:
    """Parse the JSON-only response returned by the LLM."""
    try:
        payload = json.loads(content)
    except json.JSONDecodeError as error:
        raise RuntimeError("Groq returned invalid JSON.") from error

    answer = payload.get("answer")
    used_show_ids = payload.get("used_show_ids")

    if not isinstance(answer, str) or not answer.strip():
        raise RuntimeError("Groq response did not contain a valid answer.")

    if not isinstance(used_show_ids, list):
        raise RuntimeError("Groq response did not contain used_show_ids.")

    clean_show_ids = [str(show_id) for show_id in used_show_ids]

    return LLMAnswer(answer=answer.strip(), used_show_ids=clean_show_ids)


def answer_with_groq(question: str, titles: list[RetrievedTitle]) -> LLMAnswer:
    """Send retrieved titles to Groq and return a parsed grounded answer."""
    load_dotenv()

    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is not set. Add it to your .env file.")

    from groq import Groq

    client = Groq(api_key=api_key)

    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_MESSAGE},
            {"role": "user", "content": build_prompt(question, titles)},
        ],
        temperature=0.1,
        max_completion_tokens=500,
    )

    content = response.choices[0].message.content

    if content is None:
        raise RuntimeError("Groq returned an empty response.")

    return parse_llm_json(content.strip())
