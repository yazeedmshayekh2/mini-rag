from ..helpers.config import Settings, get_settings
from ..models.enums import ResponseEnum


class BaseController:
    def __init__(self, app_settings: Settings = get_settings()):
        self.app_settings = app_settings
        self.response_enum = ResponseEnum
