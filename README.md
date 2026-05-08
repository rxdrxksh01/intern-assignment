# Netflix Catalog Q&A System

This project is a small backend system for searching and asking questions about a Netflix catalogue dataset.

It has three main parts:

1. **Data ingestion** — cleans the raw Netflix CSV and stores it in SQLite.
2. **Structured API** — provides FastAPI endpoints for title search, title lookup, and catalogue stats.
3. **RAG Q&A** — retrieves relevant catalogue titles from Chroma and uses Groq to answer questions with source `show_id`s.

The source dataset is:

```text
data/netflix_titles.csv
```

Generated files such as `data/netflix.db`, `data/chroma_db/`, `.env`, and `.venv/` are not committed because they can be rebuilt locally.

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
- Optional demo UI: Streamlit

---

## Setup

Clone the repository:

```bash
git clone <your-repo-url>
cd intern-assignment
```

Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install backend dependencies:

```bash
pip install -r requirements.txt
```

Create a local environment file:

```bash
cp .env.example .env
```

Add your Groq key in `.env`:

```env
GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL=llama-3.3-70b-versatile
```

Do not commit `.env`.

---

## How to Run

### 1. Run ingestion

```bash
python ingest.py
```

This reads the raw CSV and creates:

```text
data/netflix.db
```

The script prints a summary report with rows read, rows loaded, rows dropped, missing values handled, and cleaning fixes applied.

### 2. Build the RAG index

```bash
python -m rag.index
```

This creates the local Chroma vector index:

```text
data/chroma_db/
```

The index stores one embedded document per Netflix title.

### 3. Start the API

```bash
uvicorn api.main:app --reload
```

The API runs at:

```text
http://127.0.0.1:8000
```

Interactive docs are available at:

```text
http://127.0.0.1:8000/docs
```

---

## API Endpoints

### Health check

```bash
curl http://127.0.0.1:8000/health
```

### List titles

```bash
curl "http://127.0.0.1:8000/titles?country=India&type=Movie&page=1&page_size=5"
```

Supported filters:

- `country`
- `release_year`
- `type`
- `rating`
- `page`
- `page_size`

### Get one title by ID

```bash
curl http://127.0.0.1:8000/titles/81075235
```

### Stats

```bash
curl http://127.0.0.1:8000/stats
```

Returns total titles, count by type, and top 10 countries.

### Ask a question

```bash
curl -X POST http://127.0.0.1:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question":"Suggest me an Indian comedy movie"}'
```

The `/ask` endpoint embeds the question, retrieves relevant titles from Chroma, sends the retrieved context to Groq, and returns an answer plus the source titles used.

---

## Optional Streamlit Demo

The Streamlit demo is only a thin UI over the FastAPI backend. It does not replace the API.

Install demo dependency:

```bash
pip install -r requirements-demo.txt
```

Start the backend first:

```bash
python ingest.py
python -m rag.index
uvicorn api.main:app --reload
```

Then run:

```bash
streamlit run demo/streamlit_app.py
```

The Streamlit sidebar lets you set the API base URL. For local use, keep:

```text
http://127.0.0.1:8000
```

For deployed use, paste the Render backend URL.

---

## Deployment Notes

For Render backend deployment, use:

```bash
pip install -r requirements.txt && python ingest.py && python -m rag.index
```

as the build command, and:

```bash
python -m uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-10000}
```

as the start command.

Set these environment variables on Render:

```env
GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL=llama-3.3-70b-versatile
PYTHON_VERSION=3.11.11
```

The RAG dependencies are lazy-loaded so the API can start quickly. The first `/ask` request after a restart can be slower because it loads the embedding model and Chroma retriever into memory.

---

## How to Test

Run the tests:

```bash
python -m pytest -q
```

Run linting:

```bash
ruff check .
```

To fix import sorting or formatting issues:

```bash
ruff check --select I --fix .
ruff format .
```

The test suite covers ingestion row dropping, metadata parsing, duplicate-content handling, filtered title listing, missing title errors, and `/ask` source output.

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

## Known Limitations

- The dataset is a 2019 Netflix snapshot, so it should not be treated as current Netflix availability.
- Missing human-facing metadata is stored as `"Unknown"`, which is useful for display but mixes missing values with normal metadata values.
- The Chroma index must be rebuilt with `python -m rag.index` after changing the database.
- The `/ask` endpoint depends on a valid Groq API key.
- The first `/ask` request after server restart can be slower because the RAG model is loaded lazily.
- Retrieval uses one document per title. This is fine for this dataset size, but a much larger catalogue would need better indexing, caching, and evaluation.
- The system answers only from the provided catalogue data. It cannot answer questions about IMDb ratings, posters, trailers, current Netflix availability, or languages unless that information exists in the dataset.
