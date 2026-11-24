from enum import Enum


class IndexStatusEnum(str, Enum):
    PENDING = "pending"  # chunks exist, never indexed (or need re-indexing)
    INDEXING = "indexing"  # a run is in progress
    INDEXED = "indexed"
    FAILED = "failed"
