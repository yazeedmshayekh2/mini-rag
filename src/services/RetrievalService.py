import logging

from bson import ObjectId

from src.stores.llm.LLMEnums import DocumentType
from src.stores.llm.LLMInterace import EmbeddingProvider
from src.stores.vectordb.VectorDBInterface import VectorStore
from src.stores.vectordb.VectorDBSchemas import (
    MetadataFilter,
    RetrievedChunk,
    SearchQuery,
)

logger = logging.getLogger(__name__)


class RetrievalService:
    """Question in, relevant chunks out. Shared by /search, /answer and evaluation."""

    def __init__(
        self,
        *,
        embedder: EmbeddingProvider,
        vector_store: VectorStore,
        collection: str,
        default_top_k: int = 5,
        score_threshold: float | None = None,
    ):
        self.embedder = embedder
        self.vector_store = vector_store
        self.collection = collection
        self.default_top_k = default_top_k
        self.score_threshold = score_threshold

    async def retrieve(
        self,
        project_id: ObjectId,
        query: str,
        *,
        top_k: int | None = None,
        asset_ids: list[ObjectId] | None = None,
    ) -> list[RetrievedChunk]:
        query = query.strip()
        if not query:
            return []

        # same model + same normalization as indexing; QUERY side of the asymmetry
        [vector] = await self.embedder.embed_text(
            [query], document_type=DocumentType.QUERY
        )

        metadata_filter = (
            MetadataFilter(any_of={"asset_id": [str(a) for a in asset_ids]})
            if asset_ids  # None or [] -> no asset filter (the adapter rejects an empty any_of)
            else None
        )

        chunks = await self.vector_store.search(
            self.collection,
            SearchQuery(
                project_id=str(project_id),
                vector=vector,
                limit=top_k or self.default_top_k,
                score_threshold=self.score_threshold,
                filter=metadata_filter,
            ),
        )
        # log shape, not content: questions can contain personal data
        logger.info(
            "Retrieved %d chunks for project %s (query_len=%d, top_k=%d)",
            len(chunks),
            project_id,
            len(query),
            top_k or self.default_top_k,
        )
        return chunks
