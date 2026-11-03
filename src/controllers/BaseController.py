from src.helpers.config import Settings, get_settings
from src.models.enums import ResponseEnum
from pathlib import Path


class BaseController:
    def __init__(self):

        self.app_settings = get_settings()

        self.response_enum = ResponseEnum

        self.base_dir = Path(__file__).parent
        self._file_dir = self.base_dir / "files"

    @property
    def file_dir(self) -> Path:
        return self._file_dir

    def __str__(self) -> str:
        return f"{self.__class__.__name__}(files_dir={self.files_dir!r})"
