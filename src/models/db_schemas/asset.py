from datetime import datetime, timezone
from typing import ClassVar, List, Optional
from bson import ObjectId
from pydantic import BaseModel, ConfigDict, Field
from pymongo import ASCENDING, IndexModel


class Asset(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    id: Optional[ObjectId] = Field(None, alias="_id")
    asset_project_id: ObjectId
    asset_type: str = Field(..., min_length=1)  # File, URL, SQL Connection, etc.
    asset_name: str = Field(..., min_length=1)
    asset_size: int = Field(ge=0, default=None)
    asset_config: dict = Field(default=None)
    asset_pushed_at: datetime = Field(default=datetime.now(timezone.utc))

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
