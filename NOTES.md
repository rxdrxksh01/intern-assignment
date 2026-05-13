# NOTES

## 1. CSV problems, fixes, and what I left

The CSV was usable, but it needed cleaning before using it for search and RAG.

Problems I found:

- `date_added` had many leading spaces and needed parsing.
- Some text fields had messy whitespace such as repeated spaces, newlines, tabs, and non-breaking spaces.
- Several optional fields were missing, especially `director`, `cast`, and `country`.
- `country`, `cast`, `director`, and `listed_in` were comma-separated multi-value fields.
- Some list fields had trailing commas, which created empty values after splitting.
- `duration` was stored as text like `90 min`, `1 Season`, or `3 Seasons`.
- I found one duplicate-content row where all cleaned fields matched another row except `show_id`.

Fixes made:

- Cleaned whitespace in text fields.
- Parsed `date_added` into `YYYY-MM-DD`.
- Parsed `release_year` as an integer.
- Split `duration` into `duration_value` and `duration_unit`.
- Converted missing user-facing metadata to `"Unknown"` for fields like director, cast, country, and rating.
- Normalized rating abbreviations: `NR` to `Not Rated` and `UR` to `Unrated`.
- Split multi-value fields into separate child tables.
- Removed empty list values and duplicate list values while preserving order.
- Dropped unusable rows and exact duplicate-content rows.

What I left:

- I did not drop rows just because optional metadata was missing. A title can still be useful without director, cast, country, rating, or date_added.
- I did not manually edit the CSV. All cleaning happens in code.
- I did not add external data such as IMDb ratings, posters, languages, or current Netflix availability because that would make the assignment less reproducible.
- I did not do fuzzy duplicate matching. I only removed exact duplicate cleaned content except `show_id`.

---

## 2. Schema decisions

I used SQLite because the dataset is small, local, and easy to rebuild.

The main table is `titles`. It stores one row per title with:

- `show_id`
- `type`
- `title`
- `release_year`
- `rating`
- `duration_value`
- `duration_unit`
- `date_added`
- `description`

I used `show_id` as the primary key because title names are not guaranteed to be unique.

For multi-value fields, I created child tables:

- `title_countries`
- `title_genres`
- `title_cast`
- `title_directors`

I did this because fields like `country`, `cast`, `director`, and `listed_in` can contain multiple values in one CSV cell. Storing them separately makes filtering and stats cleaner. For example, a title with `United States, India` should count under both countries.

Each child table has a `position` column to preserve the original order from the CSV, especially for cast and directors.

---

## 3. RAG document design

I used one RAG document per Netflix title. I did not chunk further because each title row is already short.

For each title, I embedded a text block containing:

- title
- type
- release year
- rating
- duration
- countries
- genres
- directors
- cast
- description

I included metadata, not only description, because users may ask questions like:

```text
Indian comedy movie
TV-MA Japanese show
movie with Vijay
light heart movie of India after 2018
```

These questions depend on country, genre, rating, type, year, and cast, not only the description.

Each Chroma document stores metadata like:

```python
{
    "show_id": "...",
    "title": "...",
    "type": "Movie",
    "release_year": 2019,
    "rating": "TV-14",
    "countries": ["India"],
    "genres": ["Comedies", "Dramas"]
}
```

I store `countries` and `genres` as lists so ChromaDB can filter them using `$contains`.

---

## 4. Moving from local SentenceTransformer to Hugging Face API

Originally, the RAG system used local SentenceTransformer embeddings.

Old flow:

```text
Text
→ local SentenceTransformer model
→ embedding vector
→ ChromaDB
```

This worked locally, but it was heavy for deployment because `sentence-transformers` pulls large ML dependencies like PyTorch.

I changed the embedding system to use Hugging Face Inference API.

New flow:

```text
Text
→ Hugging Face Inference API
→ embedding vector
→ ChromaDB
```

The embedding model is still:

```text
sentence-transformers/all-MiniLM-L6-v2
```

but the model is not loaded inside the backend anymore.

This made deployment lighter because the backend only needs the lightweight Hugging Face client, not the full local embedding model stack.

I also kept manual L2 normalization because the old local SentenceTransformer flow used normalized embeddings. This keeps retrieval behavior consistent.

---

## 5. Chroma indexing flow

When I run:

```bash
python -m rag.index
```

the system:

1. Loads cleaned Netflix titles from SQLite.
2. Converts each title into a RAG document.
3. Sends document text to Hugging Face Inference API.
4. Receives an embedding vector.
5. Normalizes the vector.
6. Stores the id, document text, metadata, and embedding in ChromaDB.

The Chroma index is stored locally in:

```text
data/chroma_db/
```

This folder is generated and should not be committed.

I also store embedding metadata such as model name and dimension so the retriever can detect mismatches if the embedding model changes.

---

## 6. AI Intelligence Layer

I added an AI Intelligence Layer before Chroma retrieval.

Old `/ask` flow:

```text
User question
→ embed raw question
→ search whole Chroma vector database
→ Groq final answer
```

New `/ask` flow:

```text
User question
→ LLM query planner
→ semantic_query + Chroma where filter
→ filtered Chroma vector search
→ Groq final answer
```

The planner returns a direct Chroma-searchable plan.

Example user query:

```text
I want light heart movie of India after 2018
```

Planner output:

```python
SearchPlan(
    semantic_query="lighthearted feel-good entertaining comedy drama",
    where={
        "$and": [
            {"countries": {"$contains": "India"}},
            {"type": "Movie"},
            {"release_year": {"$gt": 2018}}
        ]
    }
)
```

This makes the retriever smarter before vector search happens.

The exact filters decide which titles are eligible. The semantic query decides which eligible titles are most relevant.

---

## 7. Why the AI layer was needed

Plain vector search is semantic, not strict.

If the user asks:

```text
Indian comedy movies
```

plain vector search may return non-Indian titles if their descriptions are semantically similar.

The AI Intelligence Layer solves this by creating a direct ChromaDB search plan:

```text
semantic_query = funny entertaining comedy movies
where = countries contains India, genres contains Comedies, type Movie
```

So ChromaDB searches only inside the correct filtered subset.

This is better than sending the raw query directly to vector search.

---

## 8. Example `/ask` flow

Example query:

```text
Suggest Bollywood comedy movies after 2018
```

Planner creates:

```python
SearchPlan(
    semantic_query="funny lighthearted entertaining comedy movies",
    where={
        "$and": [
            {"countries": {"$contains": "India"}},
            {"genres": {"$contains": "Comedies"}},
            {"type": "Movie"},
            {"release_year": {"$gt": 2018}}
        ]
    }
)
```

Then the retriever does:

```text
Embed semantic_query with Hugging Face
Search ChromaDB using query embedding + where filter
Return matching titles
```

Then Groq receives only retrieved catalogue titles and writes the final grounded answer.

---

## 9. RAG and LLM guardrails

The final answer prompt tells Groq:

- Use only provided catalogue sources.
- Do not use outside knowledge.
- Do not invent titles, actors, countries, ratings, years, or plot details.
- Return JSON with `answer` and `used_show_ids`.
- Only cite `show_id`s actually used in the answer.

The API then returns only the sources listed in `used_show_ids`.

This prevents the API from showing every retrieved title as a source if the answer only used some of them.

---

## 10. What would break at 100,000 titles?

At 100,000 titles, the current design would still work conceptually, but these parts would need improvement:


- Rebuilding the full Chroma index every time would be slow. I would make indexing incremental and only re-embed changed rows.
- Local Chroma storage may not be ideal for production. I would consider a managed vector store or a more controlled indexing pipeline.
- LLM latency and cost would matter more. I would cache common answers and keep retrieved context smaller.
- SQLite is good for this assignment and dataset size, but at larger production scale I would consider PostgreSQL because it handles concurrent access, indexing, backups, and production operations better.

---

## 11. AI usage

I used AI tools while building this project.

I used AI for:

- planning the ingestion package structure
- drafting first versions of helper functions
- discussing cleaning choices like `"Unknown"` vs `NULL`
- comparing schema options for multi-value fields
- drafting parts of the FastAPI and RAG scaffolding
- reviewing prompts and source-grounding behavior
- debugging deployment issues
- designing the AI Intelligence Layer before Chroma retrieval

I changed AI-generated output in multiple places instead of accepting it blindly.

One example was the RAG prompt and source handling. The first version returned all retrieved titles as sources, even when the answer only used some of them. I changed the prompt to require a JSON response with `answer` and `used_show_ids`, added guardrails against outside knowledge and invented metadata, and updated the API to return only the titles listed in `used_show_ids`.

Another example was the AI Intelligence Layer. I first considered rule-based normalization and tool-based approaches, but I kept the final implementation simpler: the LLM directly generates a Chroma-searchable plan, and Python only validates and executes it.

I also rejected suggestions that felt unnecessary for this assignment, such as MinMax scaling numeric fields, adding many boolean quality-flag columns, using a full framework like LangChain, or adding fuzzy duplicate matching without time to evaluate it.

I ran the code, checked outputs, and adjusted decisions based on actual behavior. I can explain the final path from CSV to SQLite, from SQLite to Chroma, from Chroma retrieval to Groq answer, and from raw query to AI-planned filtered retrieval.

---

## 12. What I would improve next

- **TMDB enrichment:** If business needs richer data, I would use TMDB to fill missing fields like unknown director, cast, language, poster, and external ratings with source/confidence tracking.

- **Fallback retrieval:** If strict filters return no results, I would show a clear “no exact match found” message and then return the closest relaxed alternatives.

- **RAG evaluation:** I would create a small evaluation set of sample questions and expected `show_id`s to measure whether retrieval quality is improving.
