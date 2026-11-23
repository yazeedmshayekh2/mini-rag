from __future__ import annotations

from typing import TYPE_CHECKING

from .VectorDBEnums import VectorDBProvider
from .VectorDBInterface import VectorStore

if TYPE_CHECKING:
    from src.helpers.config import Settings


class VectorDBProviderFactory:
    def __init__(self, settings: Settings):
        self.settings = settings

    def create(self) -> VectorStore:
        """Create (but do NOT connect) the configured vector store."""
        s = self.settings
        match s.VECTOR_DB_BACKEND:
            case VectorDBProvider.QDRANT:
                from .providers.QdrantProvider import QdrantProvider

                return QdrantProvider(
                    url=s.QDRANT_URL,
                    api_key=(
                        s.QDRANT_API_KEY.get_secret_value()
                        if s.QDRANT_API_KEY
                        else None
                    ),
                    timeout=s.QDRANT_TIMEOUT,
                    upsert_batch_size=s.QDRANT_UPSERT_BATCH_SIZE,
                )

            case _:
                raise ValueError(
                    f"Unsupported vector DB backend: {s.VECTOR_DB_BACKEND}"
                )
