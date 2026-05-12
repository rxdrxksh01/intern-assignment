"""Build a persistent Chroma vector index for Netflix title documents."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import TypeVar

import chromadb

from rag.config import (
    CHROMA_COLLECTION_NAME,
    CHROMA_PATH,
    EMBEDDING_MODEL_NAME,
    RAG_BATCH_SIZE,
)
from rag.documents import TitleDocument, load_title_documents
from rag.embeddings import get_hf_client, embed_texts

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
    hf_client: object,
    documents: list[TitleDocument],
) -> None:
    """Embed documents in batches and add them to Chroma."""
    expected_dimension: int | None = None

    for batch_number, document_batch in enumerate(
        batched(documents, RAG_BATCH_SIZE), start=1
    ):
        texts = [document.text for document in document_batch]
        embeddings = embed_texts(hf_client, texts)

        if not embeddings:
            raise RuntimeError(f"No embeddings generated for batch {batch_number}.")

        batch_dimension = len(embeddings[0])

        if expected_dimension is None:
            expected_dimension = batch_dimension

            collection.modify(
                metadata={
                    "embedding_model": EMBEDDING_MODEL_NAME,
                    "embedding_dimension": expected_dimension,
                }
            )

            logger.info(
                "Embedding metadata saved: model=%s, dimension=%d",
                EMBEDDING_MODEL_NAME,
                expected_dimension,
            )

        elif batch_dimension != expected_dimension:
            raise RuntimeError(
                f"Embedding dimension changed in batch {batch_number}: "
                f"expected {expected_dimension}, got {batch_dimension}."
            )

        collection.add(
            ids=[document.show_id for document in document_batch],
            documents=texts,
            metadatas=[document.metadata for document in document_batch],
            embeddings=embeddings,
        )

        logger.info(
            "Batch %d indexed (%d documents)", batch_number, len(document_batch)
        )


def build_index() -> None:
    """Embed all title documents and save them in a local Chroma collection."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    documents = load_title_documents()

    if not documents:
        raise ValueError("No title documents found. Run `python ingest.py` first.")

    reset_chroma_directory(CHROMA_PATH)

    hf_client = get_hf_client()
    client = chromadb.PersistentClient(path=str(CHROMA_PATH))
    collection = client.get_or_create_collection(name=CHROMA_COLLECTION_NAME)

    add_documents_to_collection(collection, hf_client, documents)

    logger.info("RAG index built")
    logger.info("Documents indexed: %s", len(documents))
    logger.info("Chroma path: %s", CHROMA_PATH)
    logger.info("Collection: %s", CHROMA_COLLECTION_NAME)
    logger.info("Embedding model: %s", EMBEDDING_MODEL_NAME)


if __name__ == "__main__":
    build_index()
