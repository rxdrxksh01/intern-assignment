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

## 2. Schema decisions

I used SQLite because the dataset is small, local, and easy to rebuild.

The main table is `titles`. It stores one row per title with `show_id`, `type`, `title`, `release_year`, `rating`, `duration_value`, `duration_unit`, `date_added`, and `description`.

I used `show_id` as the primary key because title names are not guaranteed to be unique.

For multi-value fields, I created child tables:

- `title_countries`
- `title_genres`
- `title_cast`
- `title_directors`

I did this because fields like `country`, `cast`, `director`, and `listed_in` can contain multiple values in one CSV cell. Storing them separately makes filtering and stats cleaner. For example, a title with `United States, India` should count under both countries.

Each child table has a `position` column to preserve the original order from the CSV, especially for cast and directors.

## 3. RAG choices

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

I included metadata, not only description, because users may ask questions like “Indian comedy movie”, “TV-MA Japanese show”, or “movie with Vijay”. Those questions depend on country, genre, rating, type, and cast.

RAG stack:
- Embedding model: `sentence-transformers/all-MiniLM-L6-v2`
- Vector store: Chroma
- LLM: Groq with `llama-3.3-70b-versatile`

I chose Chroma because it stores documents, embeddings, ids, and metadata together. I did not use LangChain because the project is small and I wanted the retrieval flow to stay easy to explain.

The `/ask` endpoint retrieves relevant titles, sends them to Groq with a guarded prompt, and returns an answer plus only the `show_id`s the LLM says it actually used. The prompt asks the model to use only catalogue sources, avoid invented metadata, and return JSON with `answer` and `used_show_ids`.

For deployment, I lazy-loaded the heavy RAG dependencies so the API server can open its port quickly. The first `/ask` request after restart can be slower, but later requests reuse the cached retriever.

## 4. What would break at 100,000 titles?

At 100,000 titles, the current design would still work conceptually, but these parts would need improvement:

- The API currently fetches child-table values title by title. At larger scale, this N+1 pattern would be slow. I would batch-fetch child values with `WHERE show_id IN (...)`.
- Rebuilding the full Chroma index every time would be slow. I would make indexing incremental and only re-embed changed rows.
- RAG quality would need evaluation. I would add a test set of questions with expected source `show_id`s.
- Local Chroma storage may not be ideal for production. I would consider a managed vector store or a more controlled indexing pipeline.
- LLM latency and cost would matter more. I would cache common answers and keep retrieved context smaller.
- Deployment would need more predictable storage and startup behavior instead of rebuilding generated artifacts in a simple build command.

## 5. AI usage

I used AI tools while building this project.

I used AI for:
- planning the ingestion package structure
- drafting first versions of helper functions
- discussing cleaning choices like `"Unknown"` vs `NULL`
- comparing schema options for multi-value fields
- drafting parts of the FastAPI and RAG scaffolding
- reviewing prompts and source-grounding behavior
- debugging deployment issues

I changed AI-generated output in multiple places instead of accepting it blindly. One example was the RAG prompt and source handling. The first version returned all retrieved titles as sources, even when the answer only used some of them. I changed the prompt to require a JSON response with `answer` and `used_show_ids`, added guardrails against outside knowledge and invented metadata, and updated the API to return only the titles listed in `used_show_ids`.

I also rejected suggestions that felt unnecessary for this assignment, such as MinMax scaling numeric fields, adding many boolean quality-flag columns, using a full framework like LangChain, or adding fuzzy duplicate matching without time to evaluate it.

I ran the code, checked outputs, and adjusted decisions based on actual behavior. I can explain the final path from CSV to SQLite, from SQLite to API response, and from Chroma retrieval to Groq answer.

## 6. What I would do with another 4 hours

With another 4 hours, I would:
- Add IMDb or TMDB metadata such as IMDb rating, poster URL, language, and external links as a separate enrichment step.
- Add a fallback for `/ask` when Groq fails, returning retrieved titles with a clear message instead of a server error.
- Add more API tests for pagination edge cases, invalid filters, and `/ask` failure cases.
- Add a small RAG evaluation file with example questions and expected source `show_id`s.
- Batch child-table lookups in `/titles` to reduce repeated SQL queries.
- Add a Docker setup so reviewers can run the project more easily.
