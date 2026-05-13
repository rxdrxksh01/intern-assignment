"""Retrieve relevant Netflix titles from the Chroma vector store."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from rag.config import CHROMA_COLLECTION_NAME, CHROMA_PATH, EMBEDDING_MODEL_NAME, RAG_TOP_K
from rag.embeddings import get_hf_client, embed_one_text


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

        self.hf_client = get_hf_client()
        self.client = chromadb.PersistentClient(path=str(CHROMA_PATH))
        self.collection = self.client.get_collection(name=CHROMA_COLLECTION_NAME)

    def _validate_query_embedding_dimension(self, query_embedding: list[float]) -> None:
        """Ensure query embedding matches the Chroma index metadata."""
        metadata = self.collection.metadata or {}

        indexed_model = metadata.get("embedding_model")
        indexed_dimension = metadata.get("embedding_dimension")

        if indexed_model and indexed_model != EMBEDDING_MODEL_NAME:
            raise RuntimeError(
                "Embedding model mismatch. "
                f"Chroma index was built with '{indexed_model}', "
                f"but current config uses '{EMBEDDING_MODEL_NAME}'. "
                "Rebuild the index with `python -m rag.index`."
            )

        if indexed_dimension is None:
            return

        try:
            expected_dimension = int(indexed_dimension)
        except (TypeError, ValueError) as error:
            raise RuntimeError(
                "Invalid embedding_dimension stored in Chroma metadata. "
                "Rebuild the index with `python -m rag.index`."
            ) from error

        actual_dimension = len(query_embedding)

        if actual_dimension != expected_dimension:
            raise RuntimeError(
                "Query embedding dimension does not match Chroma index. "
                f"Expected {expected_dimension}, got {actual_dimension}. "
                "Rebuild the index with `python -m rag.index`."
            )

    def retrieve(
        self,
        question: str,
        top_k: int = RAG_TOP_K,
        where_filter: dict[str, Any] | None = None,
    ) -> list[RetrievedTitle]:
            """Return the most relevant catalogue titles for a question."""
            query_embedding = embed_one_text(self.hf_client, question)
            self._validate_query_embedding_dimension(query_embedding)

            query_args: dict[str, Any] = {
                "query_embeddings": [query_embedding],
                "n_results": top_k,
                "include": ["documents", "metadatas", "distances"],
            }

            if where_filter:
                query_args["where"] = where_filter

            result = self.collection.query(**query_args)

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