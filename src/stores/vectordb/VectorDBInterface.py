from abc import ABC, abstractmethod
from collections.abc import Sequence

from ..AsyncResource import AsyncResource
from .VectorDBSchemas import (
    CollectionInfo,
    CollectionSpec,
    MetadataFilter,
    RetrievedChunk,
    SearchQuery,
    VectorRecord,
)


class VectorStore(AsyncResource):

    # ---------- lifecycle ----------
    @abstractmethod
    async def connect(self) -> None: ...

    # ---------- collection management ----------
    @abstractmethod
    async def ensure_collection(self, spec: CollectionSpec) -> None:
        """Create the collection if missing. If it exists, verify its config matches the spec
        (raise CollectionConfigMismatchError otherwise). Idempotent: safe at every startup.
        """

    @abstractmethod
    async def get_collection_info(self, name: str) -> CollectionInfo: ...

    @abstractmethod
    async def delete_collection(self, name: str) -> None: ...

    # ---------- data (always tenant-scoped) ----------
    @abstractmethod
    async def upsert(self, collection: str, records: Sequence[VectorRecord]) -> None:
        """Insert or overwrite by id. Same id → same point, so re-indexing never duplicates."""

    @abstractmethod
    async def search(
        self, collection: str, query: SearchQuery
    ) -> list[RetrievedChunk]: ...

    @abstractmethod
    async def delete(
        self, collection: str, project_id: str, filter: MetadataFilter | None = None
    ) -> None:
        """Delete a project's points, or a subset of them (e.g. one asset)."""

    @abstractmethod
    async def count(
        self, collection: str, project_id: str, filter: MetadataFilter | None = None
    ) -> int: ...

    # ---------- convenience ----------
    async def __aenter__(self):
        await self.connect()
        return self
