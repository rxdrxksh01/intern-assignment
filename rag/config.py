"""Configuration values for the RAG pipeline."""

from __future__ import annotations

import os
from pathlib import Path

CHROMA_PATH = Path(os.environ.get("CHROMA_PATH", "data/chroma_db"))
CHROMA_COLLECTION_NAME = os.environ.get("CHROMA_COLLECTION_NAME", "netflix_titles")
EMBEDDING_MODEL_NAME = os.environ.get(
    "EMBEDDING_MODEL_NAME",
    "sentence-transformers/all-MiniLM-L6-v2",
)
HF_API_TOKEN = os.environ.get("HF_API_TOKEN", "")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
RAG_BATCH_SIZE = int(os.environ.get("RAG_BATCH_SIZE", "128"))
RAG_TOP_K = int(os.environ.get("RAG_TOP_K", "5"))
