import re

from .VectorDBEnums import DistanceMetric, PayloadFieldType
from .VectorDBSchemas import CollectionSpec


def chunks_collection_name(
    prefix: str, embedding_model_id: str, vector_size: int
) -> str:
    """One collection per embedding space, e.g. 'chunks_bge_m3_1024'.
    Switching models creates a NEW collection; vectors from different models are never mixed.
    """
    safe_model = re.sub(r"[^a-zA-Z0-9]+", "_", embedding_model_id).strip("_").lower()
    return f"{prefix}_{safe_model}_{vector_size}"


def chunks_collection_spec(
    prefix: str, embedding_model_id: str, vector_size: int
) -> CollectionSpec:
    """The app's decision about how chunks are stored: which metadata fields get indexed."""
    return CollectionSpec(
        name=chunks_collection_name(prefix, embedding_model_id, vector_size),
        vector_size=vector_size,
        distance=DistanceMetric.COSINE,
        indexed_fields={
            "asset_id": PayloadFieldType.KEYWORD,  # filter/delete by document
            "chunk_order": PayloadFieldType.INTEGER,  # fetch neighbouring chunks later
        },
    )
