# NOTES

## 1. CSV problems, fixes, and what I left

The CSV was usable, but it needed cleaning before using it for search or RAG.

Main problems found:
- `date_added` had many leading-space issues, so dates needed trimming before parsing.
- Some text fields had messy whitespace such as newlines, tabs, repeated spaces, and non-breaking spaces.
- Optional metadata was missing in many rows, especially `director`, `cast`, and `country`.
- `country`, `cast`, `director`, and `listed_in` were comma-separated multi-value fields.
- Some country values had trailing commas, which created empty values after splitting.
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
- Removed empty list values and duplicate list values while keeping original order.
- Dropped only unusable rows or exact duplicate-content rows.

What I left:
- I did not drop rows just because director, cast, country, rating, or date_added was missing. Those fields are useful but not required to identify a title.
- I did not manually edit the CSV; all cleaning happens in code.
- I did not add external data such as IMDb ratings, posters, languages, or current Netflix availability because that would add new dependencies and make the assignment harder to reproduce.
- I did not try fuzzy duplicate matching. I only removed rows where cleaned content matched exactly except `show_id`.

## 2. Schema decisions

I used SQLite because the dataset is small, local, and easy to rebuild.

The main table is `titles`. It stores one row per title with fields like `show_id`, `type`, `title`, `release_year`, `rating`, `duration_value`, `duration_unit`, `date_added`, and `description`.

I used `show_id` as the primary key because title names are not guaranteed to be unique.

For multi-value fields, I created child tables:

- `title_countries`
- `title_genres`
- `title_cast`
- `title_directors`

I did this because fields like `country`, `cast`, `director`, and `listed_in` can contain multiple values in one CSV cell. Storing them in child tables makes filtering and stats cleaner. For example, a title with `United States, India` should count under both countries.

Each child table also has a `position` column. This preserves the original order from the CSV, which is useful for fields like cast and directors.

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

I included metadata, not only description, because users may ask questions like “Indian comedy movie”, “TV-MA Japanese show”, or “movie with Vijay”. Those answers depend on country, genre, rating, cast, and type.

I used:

- Embedding model: `sentence-transformers/all-MiniLM-L6-v2`
- Vector store: Chroma
- LLM: Groq with `llama-3.3-70b-versatile`

I chose Chroma instead of only numpy because it stores documents, embeddings, ids, and metadata together. I did not use a heavier framework like LangChain because the project is small and I wanted the retrieval flow to stay easy to explain.

The `/ask` endpoint retrieves relevant titles, sends them to Groq with guardrails, and returns the answer plus only the `show_id`s the LLM says it actually used. The prompt asks the model to use only catalogue sources and return JSON with `answer` and `used_show_ids`.

## 4. What would break at 100,000 titles?

At 100,000 titles, the current design would still work conceptually, but several parts would need improvement:

- API list responses would need stronger pagination and possibly more indexes.
- The current API fetches child-table values title by title, which is simple but creates many queries per page. At larger scale I would batch-fetch child values using `WHERE show_id IN (...)`.
- Rebuilding the full Chroma index every time would become slow. I would make indexing incremental and only re-embed changed rows.
- RAG quality would need evaluation. I would add a small test set of questions and expected source titles.
- Local Chroma storage may be enough for development, but for production I would consider a managed vector store or a more controlled indexing pipeline.
- LLM cost and latency would matter more. I would cache common answers and reduce context size more carefully.

## 5. AI usage

I used AI tools while building this project.

I used AI for:
- planning the ingestion structure
- drafting some first versions of helper functions
- discussing cleaning choices like `Unknown` vs `NULL`
- comparing SQLite schema options for multi-value fields
- drafting API and RAG route structure
- reviewing prompts and source-grounding behavior
- checking whether code looked over-engineered

I did not accept everything blindly. I rejected or changed suggestions that felt too generic or too heavy, including:
- MinMax scaling numeric fields
- many boolean data-quality columns
- full rating whitelists
- putting RAG search text into ingestion
- returning all retrieved RAG sources even when the LLM did not use them

I changed AI-generated output in multiple places instead of accepting it blindly. One example was the RAG prompt and source handling. The first version returned all retrieved titles as sources, even when the answer only used some of them. I changed the prompt to require a JSON response with `answer` and `used_show_ids`, added guardrails against outside knowledge and invented metadata, and updated the API to return only the titles listed in `used_show_ids`. This made the `/ask` response more honest because the returned sources now match the answer.

I also ran the code, checked outputs, and adjusted decisions based on actual behavior. I would be able to explain the final code path from CSV to SQLite, from SQLite to API, and from Chroma retrieval to Groq answer.

## 6. What I would do with another 4 hours

With another 4 hours, I would improve:

- Add IMDb/TMDB metadata such as IMDb rating, poster URL, language, and maybe runtime validation, but only as a separate enrichment step so the original CSV pipeline stays reproducible.
- Add a fallback for `/ask` when Groq fails, such as returning the retrieved titles with a clear message instead of a 500 error.

