from enum import Enum


class ResponseEnum(Enum):

    FILE_VALIDATION_SUCCESS = "file_validate_successfully"
    FILE_UPLOAD_SUCESS = "file_upload_success"
    FILE_UPLOAD_FAILED = "file_upload_failed"
    FILE_TYPE_NOT_SUPPORTED = "file_type_not_supported"
    FILE_SIZE_EXCEEDED = "file_size_exceeded"

    FILE_PROCESS_SUCCESS = "file_processing_success"
    FILE_PROCESS_FAILED = "file_processing_failed"
