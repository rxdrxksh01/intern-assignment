# Netflix Catalog Q&A System

This project is a backend system for searching and asking questions about a Netflix catalogue dataset.

It has three main parts:

1. Ingestion: cleans the raw Netflix CSV and stores it in SQLite.
2. Structured API: provides endpoints to browse titles, filter titles, fetch one title, and view stats.
3. RAG Q&A: retrieves relevant catalogue titles from Chroma and uses Groq to answer questions with source `show_id`s.

The source dataset is:

```text
data/netflix_titles.csv
```

Generated files like the SQLite database and Chroma vector index are not committed because they can be rebuilt locally.

---

## Tech Stack

- Python 3.10+
- SQLite
- FastAPI
- Chroma
- sentence-transformers
- Groq
- pytest
- ruff

---

## Project Structure

```text
.
├── ingest.py
├── ingestion/
│   ├── cleaning.py
│   ├── database.py
│   ├── duplicates.py
│   ├── models.py
│   └── pipeline.py
├── api/
│   ├── ask.py
│   ├── database.py
│   ├── main.py
│   ├── schemas.py
│   └── titles.py
├── rag/
│   ├── config.py
│   ├── documents.py
│   ├── index.py
│   ├── llm.py
│   ├── retriever.py
│   └── service.py
├── tests/
│   ├── test_api.py
│   └── test_ingestion.py
├── data/
│   └── netflix_titles.csv
├── NOTES.md
├── requirements.txt
└── README.md
```

---

## Setup

Clone the repository:

```bash
git clone <your-repo-url>
cd intern-assignment
```

Create a virtual environment:

```bash
python3 -m venv .venv
```

Activate the virtual environment:

```bash
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

---

## Environment Variables

Create a local `.env` file:

```bash
cp .env.example .env
```

Open `.env` and add your Groq API key:

```env
GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL=llama-3.3-70b-versatile
```

The Groq API key is required for the `/ask` endpoint.

Do not commit `.env`.

---

## Run Data Ingestion

Run this command from the project root:

```bash
python ingest.py
```

This reads:

```text
data/netflix_titles.csv
```

and creates:

```text
data/netflix.db
```

The ingestion script prints a summary report with:

- rows read
- rows loaded
- rows dropped
- missing values handled
- cleaning fixes applied

Example output:

```text
Ingestion complete
------------------
Database written: data/netflix.db
Rows read:        6234
Rows loaded:      6233
Rows dropped:     1
```

The generated SQLite database is ignored by Git because it can be rebuilt.

---

## Build the RAG Index

After ingestion, build the local Chroma vector index:

```bash
python -m rag.index
```

This reads the cleaned SQLite database, builds one searchable document per title, embeds each document using `sentence-transformers/all-MiniLM-L6-v2`, and stores the vectors in:

```text
data/chroma_db/
```

The Chroma index is ignored by Git because it can be rebuilt.

If the CSV or database changes, rerun:

```bash
python ingest.py
python -m rag.index
```

---

## Run the API Server

Start the FastAPI server:

```bash
uvicorn api.main:app --reload
```

The API runs at:

```text
http://127.0.0.1:8000
```

Interactive API docs are available at:

```text
http://127.0.0.1:8000/docs
```

---

## API Endpoints

### Health Check

```bash
curl http://127.0.0.1:8000/health
```

Example response:

```json
{"status":"ok"}
```

---

### List Titles

```bash
curl "http://127.0.0.1:8000/titles?page=1&page_size=5"
```

Supported query filters:

- `country`
- `release_year`
- `type`
- `rating`
- `page`
- `page_size`

Example:

```bash
curl "http://127.0.0.1:8000/titles?country=India&type=Movie&page=1&page_size=5"
```

This returns paginated title results with countries, genres, cast, and directors.

---

### Get One Title

```bash
curl http://127.0.0.1:8000/titles/81075235
```

This returns one title by `show_id`.

---

### Catalogue Stats

```bash
curl http://127.0.0.1:8000/stats
```

This returns:

- total title count
- count by type
- top countries

---

### Ask a Question

```bash
curl -X POST http://127.0.0.1:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question":"Suggest me an Indian comedy movie"}'
```

The `/ask` endpoint:

1. embeds the user question
2. retrieves relevant titles from Chroma
3. sends the retrieved titles to Groq with a grounded prompt
4. returns an answer plus the source titles used

Example response:

```json
{
  "answer": "Good matches are Brahman Naman, Time Please, 15-Aug, and Rajnigandha. They are all Indian movies listed under Comedies, so they fit your request.",
  "sources": [
    {
      "show_id": "80097355",
      "title": "Brahman Naman"
    },
    {
      "show_id": "80201815",
      "title": "Time Please"
    },
    {
      "show_id": "81033429",
      "title": "15-Aug"
    },
    {
      "show_id": "81213896",
      "title": "Rajnigandha"
    }
  ]
}
```

---

## Run Tests

Run the test suite:

```bash
python -m pytest -q
```

The tests cover important behavior such as:

- dropping unusable ingestion rows
- parsing metadata fields
- duplicate-content handling
- structured filtering
- 404 handling
- `/ask` returning an answer with sources

---

## Linting

Run ruff:

```bash
ruff check .
```

To auto-fix import sorting and formatting issues:

```bash
ruff check --select I --fix .
ruff format .
```

---

## Generated Files

These files are generated locally and should not be committed:

```text
.env
.venv/
data/netflix.db
data/chroma_db/
__pycache__/
.pytest_cache/
.ruff_cache/
```

---

## Known Points


- Missing human-facing metadata is stored as `"Unknown"`, which is useful for display but means missing values are mixed with normal metadata values.
- The Chroma index must be rebuilt with `python -m rag.index` after changing the database.
- Retrieval uses one document per title. This works for this dataset size, but a much larger catalogue would need more optimized indexing and evaluation.
