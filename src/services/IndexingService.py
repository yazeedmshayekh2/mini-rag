import logging
import time
from dataclasses import dataclass, field
from enum import Enum

from bson import ObjectId

from src.models import AssetModel, ChunkModel
from src.models.db_schemas import Asset, DataChunk
from src.models.enums import IndexStatusEnum
from src.stores.llm.LLMEnums import DocumentType
from src.stores.llm.LLMInterace import EmbeddingProvider
from src.stores.vectordb.VectorDBInterface import VectorStore
from src.stores.vectordb.VectorDBSchemas import MetadataFilter, VectorRecord

logger = logging.getLogger(__name__)


class IndexOutcome(str, Enum):
    INDEXED = "indexed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass(frozen=True, slots=True)
class AssetIndexResult:
    asset_id: str
    asset_name: str
    outcome: IndexOutcome
    indexed_chunks: int = 0
    detail: str | None = None  # error message or skip reason
    duration_s: float = 0.0


@dataclass(slots=True)
class IndexReport:
    project_id: str
    collection: str
    results: list[AssetIndexResult] = field(default_factory=list)

    def _with(self, outcome: IndexOutcome) -> list[AssetIndexResult]:
        return [r for r in self.results if r.outcome is outcome]

    @property
    def indexed(self) -> list[AssetIndexResult]:
        return self._with(IndexOutcome.INDEXED)

    @property
    def failed(self) -> list[AssetIndexResult]:
        return self._with(IndexOutcome.FAILED)

    @property
    def skipped(self) -> list[AssetIndexResult]:
        return self._with(IndexOutcome.SKIPPED)

    @property
    def total_chunks(self) -> int:
        return sum(r.indexed_chunks for r in self.results)


class IndexingService:
    """Moves an asset's chunks from Mongo into the vector store. Knows nothing about HTTP."""

    def __init__(
        self,
        *,
        chunk_model: ChunkModel,
        asset_model: AssetModel,
        embedder: EmbeddingProvider,
        vector_store: VectorStore,
        collection: str,
        page_size: int = 64,
    ):
        self.chunk_model = chunk_model
        self.asset_model = asset_model
        self.embedder = embedder
        self.vector_store = vector_store
        self.collection = collection
        self.page_size = page_size

    # ---------- project level: pick assets, isolate failures ----------
    async def index_project(
        self, project_id: ObjectId, *, force: bool = False
    ) -> IndexReport:
        assets = await self.asset_model.get_all_project_assets(
            asset_project_id=project_id
        )
        report = IndexReport(project_id=str(project_id), collection=self.collection)

        for asset in assets:
            if not force and self._is_up_to_date(asset):
                report.results.append(self._skipped(asset, "up to date"))
                continue
            report.results.append(await self.index_asset(project_id, asset))

        logger.info(
            "Indexed project %s: %d indexed, %d failed, %d skipped, %d chunks",
            project_id,
            len(report.indexed),
            len(report.failed),
            len(report.skipped),
            report.total_chunks,
        )
        return report

    # ---------- asset level: the unit of work ----------
    async def index_asset(self, project_id: ObjectId, asset: Asset) -> AssetIndexResult:
        started = time.perf_counter()

        if not await self.asset_model.try_claim_indexing(asset.id, self.collection):
            return self._skipped(asset, "already being indexed")

        indexed = 0
        try:
            # 1. replace, not append: remove this asset's old vectors (no ghosts)
            await self.vector_store.delete(
                self.collection,
                project_id=str(project_id),
                filter=MetadataFilter(equals={"asset_id": str(asset.id)}),
            )
            # 2. stream pages: memory stays flat regardless of asset size
            async for page in self.chunk_model.iter_asset_chunks(
                project_id, asset.id, page_size=self.page_size
            ):
                indexed += await self._index_page(project_id, asset, page)

        except Exception as e:  # NOT BaseException: let CancelledError through
            error = f"{type(e).__name__}: {e}"
            logger.exception(
                "Indexing failed for asset %s after %d chunks", asset.id, indexed
            )
            await self.asset_model.mark_failed(asset.id, error)
            return AssetIndexResult(
                asset_id=str(asset.id),
                asset_name=asset.asset_name,
                outcome=IndexOutcome.FAILED,
                indexed_chunks=indexed,
                detail=error,
                duration_s=time.perf_counter() - started,
            )

        await self.asset_model.mark_indexed(asset.id, self.collection, indexed)
        return AssetIndexResult(
            asset_id=str(asset.id),
            asset_name=asset.asset_name,
            outcome=IndexOutcome.INDEXED,
            indexed_chunks=indexed,
            duration_s=time.perf_counter() - started,
        )

    # ---------- page level: embed + upsert ----------
    async def _index_page(
        self, project_id: ObjectId, asset: Asset, page: list[DataChunk]
    ) -> int:
        vectors = await self.embedder.embed_text(
            [c.chunk_text for c in page], document_type=DocumentType.DOCUMENT
        )
        records = [
            self._to_record(project_id, asset, chunk, vector)
            for chunk, vector in zip(page, vectors, strict=True)
        ]
        await self.vector_store.upsert(self.collection, records)
        return len(records)

    # ---------- mapping: Mongo world → vector world ----------
    @staticmethod
    def _to_record(
        project_id: ObjectId, asset: Asset, chunk: DataChunk, vector: list[float]
    ) -> VectorRecord:
        return VectorRecord(
            id=str(chunk.id),  # deterministic: same chunk → same point
            project_id=str(project_id),  # tenant key = Mongo _id, never the public name
            vector=vector,
            text=chunk.chunk_text,  # original text: what the LLM will read
            metadata={
                **chunk.chunk_metadata,  # loader metadata first...
                "asset_id": str(
                    asset.id
                ),  # ...our keys last, so they can't be overwritten
                "asset_name": asset.asset_name,
                "chunk_order": chunk.chunk_order,
            },
        )

    def _is_up_to_date(self, asset: Asset) -> bool:
        return (
            asset.asset_index_status == IndexStatusEnum.INDEXED
            and asset.asset_index_collection == self.collection
        )

    @staticmethod
    def _skipped(asset: Asset, reason: str) -> AssetIndexResult:
        return AssetIndexResult(
            asset_id=str(asset.id),
            asset_name=asset.asset_name,
            outcome=IndexOutcome.SKIPPED,
            detail=reason,
        )
