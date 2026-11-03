from fastapi import UploadFile

from .BaseController import BaseController


class DataController(BaseController):
    def __init__(self):
        super().__init__()

        self.size_scale = 1024 * 1024

    def validate_uploaded_file(self, file: UploadFile):

        if file.content_type not in self.app_settings.FILE_ALLOWED_TYPES:
            return False, self.response_enum.FILE_TYPE_NOT_SUPPORTED.value

        if file.size > self.app_settings.FILE_MAX_SIZE * self.size_scale:
            return False, self.response_enum.FILE_SIZE_EXCEEDED.value

        return True, self.response_enum.FILE_UPLOAD_SUCESS.value
