"""Retrieve relevant Netflix titles from the Chroma vector store."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from rag.config import CHROMA_COLLECTION_NAME, CHROMA_PATH, RAG_TOP_K
from rag.embeddings import _get_hf_client, embed_one_text


@dataclass
class RetrievedTitle:
    """A title retrieved from the vector store."""

    show_id: str
    title: str
    text: str
    metadata: dict[str, Any]
    distance: float


class TitleRetriever:
    """Chroma-backed retriever for Netflix title documents."""

    def __init__(self) -> None:
        """Load Chroma and the HF client only when retrieval is needed."""
        if not CHROMA_PATH.exists():
            raise FileNotFoundError(
                "Chroma index not found. Run `python -m rag.index` first."
            )

        import chromadb

        self.hf_client = _get_hf_client()
        self.client = chromadb.PersistentClient(path=str(CHROMA_PATH))
        self.collection = self.client.get_collection(name=CHROMA_COLLECTION_NAME)

    def retrieve(self, question: str, top_k: int = RAG_TOP_K) -> list[RetrievedTitle]:
        """Return the most relevant catalogue titles for a question."""
        query_embedding = embed_one_text(self.hf_client, question)

        result = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )

        ids = result["ids"][0]
        documents = result["documents"][0]
        metadatas = result["metadatas"][0]
        distances = result["distances"][0]

        return [
            RetrievedTitle(
                show_id=str(item_id),
                title=str(metadata.get("title", "")),
                text=str(document),
                metadata=dict(metadata),
                distance=float(distance),
            )
            for item_id, document, metadata, distance in zip(
                ids,
                documents,
                metadatas,
                distances,
                strict=True,
            )
        ]
