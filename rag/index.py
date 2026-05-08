"""Build a persistent Chroma vector index for Netflix title documents."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import TypeVar

import chromadb
from sentence_transformers import SentenceTransformer

from rag.config import (
    CHROMA_COLLECTION_NAME,
    CHROMA_PATH,
    EMBEDDING_MODEL_NAME,
    RAG_BATCH_SIZE,
)
from rag.documents import TitleDocument, load_title_documents

logger = logging.getLogger(__name__)

T = TypeVar("T")


def reset_chroma_directory(path: Path) -> None:
    """Remove an old local Chroma index before rebuilding."""
    if path.exists():
        shutil.rmtree(path)

    path.mkdir(parents=True, exist_ok=True)


def batched(items: list[T], batch_size: int) -> list[list[T]]:
    """Split a list into fixed-size batches."""
    return [
        items[index : index + batch_size] for index in range(0, len(items), batch_size)
    ]


def add_documents_to_collection(
    collection: chromadb.Collection,
    model: SentenceTransformer,
    documents: list[TitleDocument],
) -> None:
    """Embed documents in batches and add them to Chroma."""
    for document_batch in batched(documents, RAG_BATCH_SIZE):
        texts = [document.text for document in document_batch]
        embeddings = model.encode(texts, normalize_embeddings=True).tolist()

        collection.add(
            ids=[document.show_id for document in document_batch],
            documents=texts,
            metadatas=[document.metadata for document in document_batch],
            embeddings=embeddings,
        )


def build_index() -> None:
    """Embed all title documents and save them in a local Chroma collection."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    documents = load_title_documents()

    if not documents:
        raise ValueError("No title documents found. Run `python ingest.py` first.")

    reset_chroma_directory(CHROMA_PATH)

    model = SentenceTransformer(EMBEDDING_MODEL_NAME)
    client = chromadb.PersistentClient(path=str(CHROMA_PATH))
    collection = client.get_or_create_collection(name=CHROMA_COLLECTION_NAME)

    add_documents_to_collection(collection, model, documents)

    logger.info("RAG index built")
    logger.info("Documents indexed: %s", len(documents))
    logger.info("Chroma path: %s", CHROMA_PATH)
    logger.info("Collection: %s", CHROMA_COLLECTION_NAME)
    logger.info("Embedding model: %s", EMBEDDING_MODEL_NAME)


if __name__ == "__main__":
    build_index()
