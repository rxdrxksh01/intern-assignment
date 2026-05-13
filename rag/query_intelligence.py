"""LLM query intelligence layer that creates direct Chroma search plans."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

from dotenv import load_dotenv

from rag.config import GROQ_MODEL


SYSTEM_MESSAGE = """
You are an AI retrieval planner for a Netflix catalogue RAG system.

Your job is NOT to answer the user.
Your job is to convert the user's natural-language question into a ChromaDB-searchable JSON plan.

Return valid JSON only.
Do not use markdown.
Do not explain.
Do not include comments.

The JSON must have exactly these top-level keys:
{
  "semantic_query": string,
  "where": object or null
}

The "semantic_query" will be embedded for vector search.
The "where" value will be passed directly to ChromaDB collection.query(where=...).

Allowed Chroma metadata fields:
- countries
- genres
- type
- rating
- release_year

Field rules:
1. countries
   - Array field.
   - Must use: {"countries": {"$contains": "<country>"}}

2. genres
   - Array field.
   - Must use: {"genres": {"$contains": "<genre>"}}

3. type
   - String field.
   - Allowed values only: "Movie", "TV Show"
   - Must use: {"type": "Movie"} or {"type": "TV Show"}

4. rating
   - String field.
   - Must use: {"rating": "<rating>"}

5. release_year
   - Integer field.
   - Allowed operators only: "$eq", "$gte", "$lte", "$gt", "$lt"
   - Example: {"release_year": {"$gte": 2018}}

Logical rules:
- Use "$and" only when all conditions must match.
- Use "$or" only when the user clearly asks for alternatives.
- Each item inside "$and" or "$or" must be a complete filter object.
- If there are multiple constraints, use explicit "$and".

Strictly forbidden in "where":
- "country"
- "genre"
- "title"
- "description"
- "cast"
- "director"
- "date_added"
- any field not listed in the allowed metadata fields

Use these exact field names:
- "countries", not "country"
- "genres", not "genre"

Domain understanding:
- "Bollywood", "desi", "Indian" means countries contains "India".
- "American", "US", "USA" means countries contains "United States".
- "Korean", "K-drama", "Kdrama" means countries contains "South Korea".
- "British", "UK" means countries contains "United Kingdom".
- "movie", "movies", "film", "films" means type "Movie".
- "series", "show", "shows", "TV series" means type "TV Show".
- "funny", "comedy", "comedies" means genre "Comedies" for movies.
- "comedy shows" or "TV comedy" means genre "TV Comedies".
- "drama movies" means genre "Dramas".
- "drama shows" means genre "TV Dramas".
- "romantic movies" means genre "Romantic Movies".
- "romantic shows" means genre "Romantic TV Shows".
- "scary" or "horror" means genre "Horror Movies".
- "thriller" means genre "Thrillers".
- "documentary" means genre "Documentaries".
- "docuseries" means genre "Docuseries".

Year handling:
- "after 2018" means {"release_year": {"$gt": 2018}}
- "from 2018" means {"release_year": {"$gte": 2018}}
- "since 2018" means {"release_year": {"$gte": 2018}}
- "before 2020" means {"release_year": {"$lte": 2020}}
- "between 2017 and 2020" means {"release_year": {"$gte": 2017, "$lte": 2020}}
- "in 2019" means {"release_year": {"$eq": 2019}}

Before returning JSON, silently self-check:
1. Is the output valid JSON?
2. Are the only top-level keys "semantic_query" and "where"?
3. Is "semantic_query" a non-empty string?
4. Is "where" either null or a valid Chroma filter?
5. Does "where" use only allowed fields?
6. Does "where" use "countries" and "genres" with "$contains"?
7. Did you avoid unsupported fields like "country", "genre", "title", "cast", or "director"?
8. If multiple filters are needed, did you wrap them inside "$and"?

Examples:

User:
Suggest Bollywood comedy movies after 2018

Correct JSON:
{
  "semantic_query": "comedy movies",
  "where": {
    "$and": [
      {"countries": {"$contains": "India"}},
      {"genres": {"$contains": "Comedies"}},
      {"type": "Movie"},
      {"release_year": {"$gt": 2018}}
    ]
  }
}

User:
Suggest Korean romantic shows

Correct JSON:
{
  "semantic_query": "romantic shows",
  "where": {
    "$and": [
      {"countries": {"$contains": "South Korea"}},
      {"genres": {"$contains": "Romantic TV Shows"}},
      {"type": "TV Show"}
    ]
  }
}

User:
Find American documentaries before 2020

Correct JSON:
{
  "semantic_query": "documentaries",
  "where": {
    "$and": [
      {"countries": {"$contains": "United States"}},
      {"genres": {"$contains": "Documentaries"}},
      {"release_year": {"$lte": 2020}}
    ]
  }
}

User:
Suggest Indian or Korean dramas

Correct JSON:
{
  "semantic_query": "dramas",
  "where": {
    "$and": [
      {
        "$or": [
          {"countries": {"$contains": "India"}},
          {"countries": {"$contains": "South Korea"}}
        ]
      },
      {"genres": {"$contains": "Dramas"}}
    ]
  }
}

User:
Suggest emotional family stories

Correct JSON:
{
  "semantic_query": "emotional family stories",
  "where": null
}
""".strip()


@dataclass
class SearchPlan:
    """Direct Chroma search plan generated by the LLM."""

    semantic_query: str
    where: dict[str, Any] | None = None


ALLOWED_FIELDS = {"countries", "genres", "type", "rating", "release_year"}
ALLOWED_LOGICAL_OPERATORS = {"$and", "$or"}
ALLOWED_YEAR_OPERATORS = {"$eq", "$gte", "$lte", "$gt", "$lt"}


def _fallback_search_plan(question: str) -> SearchPlan:
    """Return semantic-only search plan if LLM planning fails."""
    return SearchPlan(semantic_query=question, where=None)


def _strip_markdown_fences(content: str) -> str:
    """Remove markdown JSON fences if the LLM accidentally returns them."""
    content = content.strip()

    if content.startswith("```json"):
        content = content.removeprefix("```json").strip()

    if content.startswith("```"):
        content = content.removeprefix("```").strip()

    if content.endswith("```"):
        content = content.removesuffix("```").strip()

    return content


def _load_json_object(content: str) -> dict[str, Any]:
    """Load a JSON object from LLM output."""
    content = _strip_markdown_fences(content)

    try:
        payload = json.loads(content)
    except json.JSONDecodeError as error:
        raise RuntimeError("Query planner returned invalid JSON.") from error

    if not isinstance(payload, dict):
        raise RuntimeError("Query planner JSON must be an object.")

    return payload


def _clean_semantic_query(value: Any, fallback_query: str) -> str:
    """Return a valid semantic query."""
    if isinstance(value, str) and value.strip():
        return value.strip()

    return fallback_query


def _is_safe_where_filter(value: Any) -> bool:
    """Return True only if the LLM produced a safe Chroma where filter."""
    if value is None:
        return True

    if not isinstance(value, dict):
        return False

    if not value:
        return False

    # Chroma filters should have one root key:
    # either one logical operator like "$and",
    # or one metadata field like "type".
    if len(value) != 1:
        return False

    key, inner_value = next(iter(value.items()))

    if key in ALLOWED_LOGICAL_OPERATORS:
        if not isinstance(inner_value, list) or not inner_value:
            return False

        return all(_is_safe_where_filter(item) for item in inner_value)

    if key not in ALLOWED_FIELDS:
        return False

    if key in {"countries", "genres"}:
        if not isinstance(inner_value, dict):
            return False

        if set(inner_value.keys()) != {"$contains"}:
            return False

        contains_value = inner_value["$contains"]

        if not isinstance(contains_value, str):
            return False

        return bool(contains_value.strip())

    if key == "type":
        return inner_value in {"Movie", "TV Show"}

    if key == "rating":
        return isinstance(inner_value, str) and bool(inner_value.strip())

    if key == "release_year":
        if isinstance(inner_value, bool):
            return False

        if isinstance(inner_value, int):
            return True

        if not isinstance(inner_value, dict) or not inner_value:
            return False

        for operator, year in inner_value.items():
            if operator not in ALLOWED_YEAR_OPERATORS:
                return False

            if isinstance(year, bool) or not isinstance(year, int):
                return False

        return True

    return False


def parse_search_plan(content: str, fallback_query: str) -> SearchPlan:
    """Parse LLM output into a safe SearchPlan."""
    payload = _load_json_object(content)

    semantic_query = _clean_semantic_query(
        payload.get("semantic_query"),
        fallback_query=fallback_query,
    )

    where = payload.get("where")

    if not _is_safe_where_filter(where):
        where = None

    return SearchPlan(semantic_query=semantic_query, where=where)


def create_search_plan(question: str) -> SearchPlan:
    """Ask the LLM to directly generate a Chroma-searchable plan."""
    load_dotenv()

    api_key = os.environ.get("GROQ_API_KEY")

    if not api_key:
        return _fallback_search_plan(question)

    from groq import Groq

    client = Groq(api_key=api_key)

    try:
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_MESSAGE},
                {"role": "user", "content": question},
            ],
            temperature=0,
            max_completion_tokens=700,
        )

        content = response.choices[0].message.content

        if content is None:
            return _fallback_search_plan(question)

        return parse_search_plan(content.strip(), fallback_query=question)

    except Exception:
        return _fallback_search_plan(question)