from datetime import datetime, timezone
from typing import ClassVar, List, Optional
from bson import ObjectId
from pydantic import BaseModel, ConfigDict, Field
from pymongo import ASCENDING, IndexModel

from src.models.enums import IndexStatusEnum


class Asset(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    id: Optional[ObjectId] = Field(None, alias="_id")
    asset_project_id: ObjectId
    asset_type: str = Field(..., min_length=1)  # File, URL, SQL Connection, etc.
    asset_name: str = Field(..., min_length=1)
    asset_size: int = Field(ge=0, default=None)
    asset_config: dict = Field(default=None)
    asset_pushed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    # ---------- indexing state ----------
    asset_index_status: IndexStatusEnum = IndexStatusEnum.PENDING
    asset_index_collection: Optional[str] = None
    asset_indexed_chunks: int = 0
    asset_indexed_at: Optional[datetime] = None
    asset_index_error: Optional[str] = None

    asset_index_started_at: Optional[datetime] = None

    INDEXES: ClassVar[List[IndexModel]] = [
        IndexModel(
            [
                ("asset_project_id", ASCENDING),
            ],
            name="asset_project_id_idx_1",
            unique=False,
        ),
        IndexModel(
            [
                ("asset_project_id", ASCENDING),
                ("asset_name", ASCENDING),
            ],
            name="asset_project_id_name_idx_1",
            unique=True,
        ),
    ]
