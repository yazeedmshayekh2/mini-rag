class VectorStoreError(Exception):
    """Base class: callers can catch this one type for any vector-DB failure."""


class VectorStoreConnectionError(VectorStoreError):
    """DB unreachable, timeout, auth failed."""


class CollectionNotFoundError(VectorStoreError):
    pass


class CollectionConfigMismatchError(VectorStoreError):
    """Collection exists but with a different vector size or distance metric."""


class VectorDimensionMismatchError(VectorStoreError):
    """A vector's length doesn't match the collection."""
