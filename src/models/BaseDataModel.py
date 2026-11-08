from ..helpers.config import Settings, get_settings
from pymongo import AsyncMongoClient


class BaseDataModel:
    def __init__(self, db_client):
        self.db_client: AsyncMongoClient = db_client
        self.app_settings: Settings = get_settings()
