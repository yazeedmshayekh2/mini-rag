from ..helpers.config import Settings, get_settings
from pymongo.asynchronous.database import AsyncDatabase


class BaseDataModel:
    def __init__(self, db: AsyncDatabase):
        self.db = db
        self.app_settings: Settings = get_settings()
