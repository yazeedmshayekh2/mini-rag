from pydantic import BaseModel

from src.models.enums import IndexStatusEnum


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
