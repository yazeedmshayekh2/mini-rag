from typing import ClassVar, Optional
from bson import ObjectId
from pydantic import BaseModel, ConfigDict, Field, field_validator
from pymongo import ASCENDING, IndexModel


class Project(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    id: Optional[ObjectId] = Field(None, alias="_id")
    project_id: str = Field(..., min_length=1)

    INDEXES: ClassVar[list[IndexModel]] = [
        IndexModel(
            [("project_id", ASCENDING)],
            name="project_id_idx_1",
            unique=True,
        )
    ]

    @field_validator("project_id")
    @classmethod
    def validate_project_id(cls, value: str) -> str:
        if not value.isalnum():
            raise ValueError("project_id must be alphanumeric")

        return value
