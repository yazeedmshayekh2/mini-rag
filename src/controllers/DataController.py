import re
from pathlib import Path

from fastapi import UploadFile

from src.controllers.ProjectController import ProjectController

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

    def generate_unique_file_path(
        self,
        orig_filename: str,
        project_id: str,
    ):
        project_path = ProjectController().get_project_path(project_id=project_id)

        cleaned_file_name = self.get_clean_filename(
            orig_filename=orig_filename,
        )

        while True:
            random_key = self.generate_random_string()
            new_file_path = project_path / f"{random_key}_{cleaned_file_name}"

            if not new_file_path.exists():
                break

        return new_file_path, random_key + "_" + cleaned_file_name

    def get_clean_filename(
        self,
        orig_filename: str,
    ):

        cleaned_file_name = orig_filename.strip().replace(" ", "_")

        cleaned_file_name = re.sub(r"[^\w.]", "", cleaned_file_name)

        return cleaned_file_name
