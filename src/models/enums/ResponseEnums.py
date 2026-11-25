from enum import Enum


class ResponseEnum(Enum):

    FILE_VALIDATION_SUCCESS = "file_validate_successfully"
    FILE_UPLOAD_SUCESS = "file_upload_success"
    FILE_UPLOAD_FAILED = "file_upload_failed"
    FILE_TYPE_NOT_SUPPORTED = "file_type_not_supported"
    FILE_SIZE_EXCEEDED = "file_size_exceeded"

    FILE_PROCESS_SUCCESS = "file_processing_success"
    FILE_PROCESS_FAILED = "file_processing_failed"

    NO_FILES_ERROR = "no_files_to_process"
    FILE_ID_ERROR = "no_file_found_with_this_id"

    PROJECT_NOT_FOUND = "project_not_found"
    INDEXING_STARTED = "indexing_started"
    INDEX_INFO_SUCCESS = "index_info_success"
    VECTORDB_UNAVAILABLE = "vectordb_unavailable"
    VECTORDB_ERROR = "vectordb_error"

    SEARCH_SUCCESS = "search_success"
    ASSET_NOT_FOUND = "asset_not_found"
    LLM_UNAVAILABLE = "llm_unavailable"
    LLM_ERROR = "llm_error"
