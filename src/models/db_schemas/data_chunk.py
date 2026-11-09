from pydantic import BaseModel, ConfigDict, Field, field_validator
from bson.objectid import ObjectId
from typing import ClassVar, List, Optional

from pymongo import ASCENDING, IndexModel


class DataChunk(BaseModel):

    model_config = ConfigDict(arbitrary_types_allowed=True)

    id: Optional[ObjectId] = Field(None, alias="_id")
    chunk_text: str = Field(
        ...,
        min_length=1,
    )
    chunk_metadata: dict
    chunk_order: int = Field(..., gt=0)
    chunk_project_id: ObjectId

    INDEXES: ClassVar[List[IndexModel]] = [
        IndexModel(
            [("chunk_project_id"), ASCENDING],
            name="chunk_project_id_idx_1",
            unique=False,
        )
    ]
