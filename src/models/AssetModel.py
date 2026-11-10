from bson import ObjectId

from .BaseDataModel import BaseDataModel
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.asynchronous.collection import AsyncCollection

from .db_schemas import Asset

from src.models.enums import DataBaseEnum


class AssetModel(BaseDataModel):
    def __init__(self, db: AsyncDatabase):
        super().__init__(db=db)
        self.collection: AsyncCollection = self.db[
            DataBaseEnum.COLLECTION_ASSET_NAME.value
        ]

    @classmethod
    async def create_instance(cls, db: AsyncDatabase):
        instance = cls(db)
        await instance.init_collection()
        return instance

    async def init_collection(self):
        return await self.collection.create_indexes(Asset.INDEXES)

    async def create_asset(self, asset: Asset):
        result = await self.collection.insert_one(
            asset.model_dump(by_alias=True, exclude_unset=True)
        )
        asset.id = result.inserted_id
        return asset

    async def get_all_project_assets(
        self,
        project_id: str,
        asset_type: str = None,
    ):
        query = {
            "asset_project_id": (
                ObjectId(project_id) if isinstance(project_id, str) else project_id
            ),
        }

        if asset_type is not None:
            query["asset_type"] = asset_type

        return await self.collection.find(query).to_list(length=None)
