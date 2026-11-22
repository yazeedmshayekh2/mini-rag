from enum import Enum


class VectorDBProvider(str, Enum):
    QDRANT = "QDRANT"


class DistanceMetric(str, Enum):
    COSINE = "cosine"
    DOT = "dot"
    EUCLIDEAN = "euclidean"


class PayloadFieldType(str, Enum):
    KEYWORD = "keyword"  # exact-match strings: ids, language, file type
    INTEGER = "integer"  # page number, chunk order
    FLOAT = "float"
    BOOL = "bool"
