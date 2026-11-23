import logging
import uuid
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager

import httpx
from qdrant_client import AsyncQdrantClient, models
from qdrant_client.http.exceptions import ResponseHandlingException, UnexpectedResponse

from ..VectorDBEnums import DistanceMetric, PayloadFieldType
from ..VectorDBExceptions import (
    CollectionConfigMismatchError,
    CollectionNotFoundError,
    VectorDimensionMismatchError,
    VectorStoreConnectionError,
    VectorStoreError,
)
from ..VectorDBInterface import VectorStore
from ..VectorDBSchemas import (
    CollectionInfo,
    CollectionSpec,
    MetadataFilter,
    RetrievedChunk,
    SearchQuery,
    VectorRecord,
)

logger = logging.getLogger(__name__)

# NEVER change this value: point ids are derived from it.
# Changing it would make every re-index create duplicates of every point.
POINT_ID_NAMESPACE = uuid.UUID("8b1e4c6a-2f3d-4e5b-9a7c-1d2e3f4a5b6c")

# Reserved payload keys. User metadata is nested under METADATA so it can never collide with these.
PROJECT_ID = "project_id"
RECORD_ID = "record_id"
TEXT = "text"
METADATA = "metadata"

_DISTANCE_TO_QDRANT = {
    DistanceMetric.COSINE: models.Distance.COSINE,
    DistanceMetric.DOT: models.Distance.DOT,
    DistanceMetric.EUCLIDEAN: models.Distance.EUCLID,
}
_DISTANCE_FROM_QDRANT = {v: k for k, v in _DISTANCE_TO_QDRANT.items()}

_FIELD_TYPE_TO_QDRANT = {
    PayloadFieldType.KEYWORD: models.PayloadSchemaType.KEYWORD,
    PayloadFieldType.INTEGER: models.PayloadSchemaType.INTEGER,
    PayloadFieldType.FLOAT: models.PayloadSchemaType.FLOAT,
    PayloadFieldType.BOOL: models.PayloadSchemaType.BOOL,
}


class QdrantProvider(VectorStore):
    def __init__(
        self,
        url: str,
        api_key: str | None = None,
        timeout: int = 30,
        upsert_batch_size: int = 256,
        hnsw_payload_m: int = 16,
    ):
        self._url = url
        self._api_key = api_key
        self._timeout = timeout
        self._upsert_batch_size = upsert_batch_size
        self._hnsw_payload_m = hnsw_payload_m

        self._client: AsyncQdrantClient | None = None
        self._vector_sizes: dict[str, int] = {}  # cache: collection name -> vector size

    # ================= lifecycle =================
    async def connect(self) -> None:
        self._client = AsyncQdrantClient(
            url=self._url, api_key=self._api_key, timeout=self._timeout
        )
        try:
            async with self._errors():
                await self._client.get_collections()  # fail fast: bad URL or key → error at startup
        except VectorStoreError:
            await self.close()
            raise
        logger.info("Connected to Qdrant at %s", self._url)

    async def close(self) -> None:
        if self._client is not None:
            await self._client.close()
            self._client = None

    @property
    def client(self) -> AsyncQdrantClient:
        if self._client is None:
            raise VectorStoreConnectionError(
                "QdrantProvider is not connected; call connect() first"
            )
        return self._client

    # ================= collection management =================
    async def ensure_collection(self, spec: CollectionSpec) -> None:
        async with self._errors():
            if await self.client.collection_exists(spec.name):
                info = await self.get_collection_info(spec.name)
                if (
                    info.vector_size != spec.vector_size
                    or info.distance != spec.distance
                ):
                    raise CollectionConfigMismatchError(
                        f"Collection '{spec.name}' has size={info.vector_size}, distance={info.distance.value}; "
                        f"expected size={spec.vector_size}, distance={spec.distance.value}"
                    )
            else:
                await self._create_collection(spec)

            # Idempotent: re-creating an existing index is a no-op.
            await self.client.create_payload_index(
                collection_name=spec.name,
                field_name=PROJECT_ID,
                field_schema=models.KeywordIndexParams(
                    type=models.KeywordIndexType.KEYWORD, is_tenant=True
                ),
            )
            for field_name, field_type in spec.indexed_fields.items():
                await self.client.create_payload_index(
                    collection_name=spec.name,
                    field_name=f"{METADATA}.{field_name}",
                    field_schema=_FIELD_TYPE_TO_QDRANT[field_type],
                )

        self._vector_sizes[spec.name] = spec.vector_size

    async def _create_collection(self, spec: CollectionSpec) -> None:
        try:
            await self.client.create_collection(
                collection_name=spec.name,
                vectors_config=models.VectorParams(
                    size=spec.vector_size,
                    distance=_DISTANCE_TO_QDRANT[spec.distance],
                ),
                # Multitenancy: no global graph; one HNSW graph per tenant (per project_id value).
                hnsw_config=models.HnswConfigDiff(m=0, payload_m=self._hnsw_payload_m),
            )
            logger.info(
                "Created Qdrant collection '%s' (size=%d)", spec.name, spec.vector_size
            )
        except UnexpectedResponse as e:
            if (
                e.status_code != 409
            ):  # 409 = another worker created it at the same moment: fine
                raise

    async def get_collection_info(self, name: str) -> CollectionInfo:
        async with self._errors():
            info = await self.client.get_collection(name)

        vectors = info.config.params.vectors
        if not isinstance(vectors, models.VectorParams):
            raise VectorStoreError(
                f"Collection '{name}' uses named vectors; QdrantProvider expects a single vector"
            )

        return CollectionInfo(
            name=name,
            vector_size=vectors.size,
            distance=_DISTANCE_FROM_QDRANT[vectors.distance],
            points_count=info.points_count or 0,
        )

    async def delete_collection(self, name: str) -> None:
        async with self._errors():
            await self.client.delete_collection(name)
        self._vector_sizes.pop(name, None)

    # ================= data =================
    async def upsert(self, collection: str, records: Sequence[VectorRecord]) -> None:
        if not records:
            return

        expected = await self._vector_size(collection)
        for record in records:  # validate everything BEFORE writing anything
            if len(record.vector) != expected:
                raise VectorDimensionMismatchError(
                    f"Record '{record.id}' has {len(record.vector)} dims; collection '{collection}' expects {expected}"
                )

        async with self._errors():
            for start in range(0, len(records), self._upsert_batch_size):
                batch = records[start : start + self._upsert_batch_size]
                await self.client.upsert(
                    collection_name=collection,
                    points=[
                        models.PointStruct(
                            id=self._point_id(r),
                            vector=r.vector,
                            payload=self._to_payload(r),
                        )
                        for r in batch
                    ],
                    wait=True,  # read-after-write consistency
                )
        logger.debug("Upserted %d records into '%s'", len(records), collection)

    async def search(self, collection: str, query: SearchQuery) -> list[RetrievedChunk]:
        async with self._errors():
            response = await self.client.query_points(
                collection_name=collection,
                query=query.vector,
                query_filter=self._build_filter(query.project_id, query.filter),
                limit=query.limit,
                score_threshold=query.score_threshold,
                with_payload=True,
                with_vectors=False,  # don't ship 1024 floats back per hit
            )
        return [self._to_chunk(point) for point in response.points]

    async def delete(
        self, collection: str, project_id: str, filter: MetadataFilter | None = None
    ) -> None:
        async with self._errors():
            await self.client.delete(
                collection_name=collection,
                points_selector=models.FilterSelector(
                    filter=self._build_filter(project_id, filter)
                ),
                wait=True,
            )

    async def count(
        self, collection: str, project_id: str, filter: MetadataFilter | None = None
    ) -> int:
        async with self._errors():
            result = await self.client.count(
                collection_name=collection,
                count_filter=self._build_filter(project_id, filter),
                exact=True,
            )
        return result.count

    # ================= translation helpers (private) =================
    @staticmethod
    def _point_id(record: VectorRecord) -> str:
        return str(uuid.uuid5(POINT_ID_NAMESPACE, f"{record.project_id}:{record.id}"))

    @staticmethod
    def _to_payload(record: VectorRecord) -> dict:
        return {
            PROJECT_ID: record.project_id,
            RECORD_ID: record.id,
            TEXT: record.text,
            METADATA: record.metadata,
        }

    @staticmethod
    def _to_chunk(point: models.ScoredPoint) -> RetrievedChunk:
        payload = point.payload or {}
        return RetrievedChunk(
            id=payload.get(RECORD_ID, str(point.id)),
            project_id=payload[PROJECT_ID],
            text=payload.get(TEXT, ""),
            score=point.score,
            metadata=payload.get(METADATA, {}),
        )

    @staticmethod
    def _build_filter(
        project_id: str, metadata_filter: MetadataFilter | None
    ) -> models.Filter:
        if not project_id:
            raise ValueError("project_id is required for every data operation")

        must: list[models.Condition] = [
            models.FieldCondition(
                key=PROJECT_ID, match=models.MatchValue(value=project_id)
            )
        ]
        if metadata_filter:
            for key, value in metadata_filter.equals.items():
                if isinstance(value, float):
                    raise ValueError(
                        f"Exact match on float field '{key}' is not supported"
                    )
                must.append(
                    models.FieldCondition(
                        key=f"{METADATA}.{key}", match=models.MatchValue(value=value)
                    )
                )
            for key, values in metadata_filter.any_of.items():
                if not values:
                    raise ValueError(f"any_of['{key}'] must not be empty")
                must.append(
                    models.FieldCondition(
                        key=f"{METADATA}.{key}", match=models.MatchAny(any=list(values))
                    )
                )
        return models.Filter(must=must)

    async def _vector_size(self, collection: str) -> int:
        if collection not in self._vector_sizes:
            self._vector_sizes[collection] = (
                await self.get_collection_info(collection)
            ).vector_size
        return self._vector_sizes[collection]

    @asynccontextmanager
    async def _errors(self) -> AsyncIterator[None]:
        """Translate Qdrant/transport exceptions into the domain error hierarchy."""
        try:
            yield
        except VectorStoreError:
            raise
        except UnexpectedResponse as e:
            if e.status_code == 404:
                raise CollectionNotFoundError(str(e)) from e
            if e.status_code in (401, 403):
                raise VectorStoreConnectionError("Qdrant rejected the API key") from e
            raise VectorStoreError(f"Qdrant returned HTTP {e.status_code}: {e}") from e
        except (ResponseHandlingException, httpx.TransportError) as e:
            raise VectorStoreConnectionError(
                f"Cannot reach Qdrant at {self._url}: {e}"
            ) from e
