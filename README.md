# Netflix Catalog Q&A System

This repo implements **Part 1 (data ingestion)** of the assignment: cleaning `data/netflix_titles.csv` and writing a normalized SQLite database to `data/netflix.db`. Design/cleaning decisions are documented in `NOTES.md`.

## Setup

Create a fresh virtualenv and install dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## How to run

Run ingestion end-to-end (CSV → cleaned SQLite DB + summary report):

```bash
python3 ingest.py
```

Outputs:
- `data/netflix.db` (generated)
- A summary report printed to stdout (rows read/loaded/dropped + cleaning stats)

## How to test

```bash
python3 -m pytest -q
```

## Known limitations

- This is a **2019 snapshot** dataset; results should not be treated as the current Netflix catalogue.
- Missing metadata is normalized to `"Unknown"` for display fields, which mixes “missing” with a normal value in the child tables (see `NOTES.md`).
- Duplicate detection only drops **exact duplicate cleaned content** (except `show_id`); it does not attempt fuzzy/near-duplicate matching.
