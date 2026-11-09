from enum import Enum


class DataBaseEnum(Enum):

    COLLECTION_PROJECT_NAME = "projects"
    COLLECTION_CHUNK_NAME = "chunks"


class PaginationEnum(Enum):

    PAGE_SIZE = 20
