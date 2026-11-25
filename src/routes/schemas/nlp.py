from pydantic import BaseModel, Field

from src.models.enums import IndexStatusEnum
from src.stores.vectordb.VectorDBSchemas import RetrievedChunk


class PushRequest(BaseModel):
    force: bool = False  # re-index assets that are already up to date


class IndexPushResponse(BaseModel):
    signal: str
    project_id: str
    status_url: str


class StatusBucket(BaseModel):
    assets: int = 0
    chunks: int = 0


class FailedAsset(BaseModel):
    asset_name: str
    error: str | None = None


class IndexInfoResponse(BaseModel):
    signal: str
    project_id: str
    collection: str
    statuses: dict[IndexStatusEnum, StatusBucket]
    vector_points: int
    is_indexing: bool
    in_sync: bool
    failed_assets: list[FailedAsset]


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2_000)
    top_k: int | None = Field(None, ge=1, le=20)  # None -> server default
    file_ids: list[str] | None = Field(None, max_length=50)  # public asset names


class SearchHit(BaseModel):
    chunk_id: str
    score: float
    text: str
    asset_name: str | None = None
    chunk_order: int | None = None
    page: int | None = None  # 1-based, for humans

    @classmethod
    def from_chunk(cls, chunk: RetrievedChunk) -> "SearchHit":
        md = chunk.metadata
        page = md.get("page")
        return cls(  # explicit whitelist: 'source'/'file_path' never leave the server
            chunk_id=chunk.id,
            score=round(chunk.score, 4),
            text=chunk.text,
            asset_name=md.get("asset_name"),
            chunk_order=md.get("chunk_order"),
            page=page + 1 if isinstance(page, int) else None,
        )


class SearchResponse(BaseModel):
    signal: str
    project_id: str
    hits: list[SearchHit]
