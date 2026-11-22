from dataclasses import dataclass, field
from typing import Any

from .VectorDBEnums import DistanceMetric, PayloadFieldType

Scalar = str | int | float | bool


@dataclass(frozen=True, slots=True)
class CollectionSpec:
    """Everything needed to create a collection, independent of any database."""

    name: str
    vector_size: int
    distance: DistanceMetric = DistanceMetric.COSINE
    indexed_fields: dict[str, PayloadFieldType] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class VectorRecord:
    """One chunk, ready to store."""

    id: str  # stable business id (the Mongo chunk _id), NOT a DB-specific id
    project_id: str  # tenant key: required, not buried in metadata
    vector: list[float]
    text: str  # ORIGINAL text (not normalized): this is what the LLM reads
    metadata: dict[str, Any] = field(
        default_factory=dict
    )  # asset_id, page, chunk_order, ...


@dataclass(frozen=True, slots=True)
class MetadataFilter:
    """A tiny, DB-neutral filter language. Each adapter translates it."""

    equals: dict[str, Scalar] = field(default_factory=dict)  # field == value
    any_of: dict[str, list[Scalar]] = field(default_factory=dict)  # field IN (values)


@dataclass(frozen=True, slots=True)
class SearchQuery:
    project_id: str
    vector: list[float]
    limit: int = 5
    score_threshold: float | None = None
    filter: MetadataFilter | None = None


@dataclass(frozen=True, slots=True)
class RetrievedChunk:
    id: str
    project_id: str
    text: str
    score: float
    metadata: dict[str, Any]


@dataclass(frozen=True, slots=True)
class CollectionInfo:
    name: str
    vector_size: int
    distance: DistanceMetric
    points_count: int
