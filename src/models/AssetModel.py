from datetime import datetime, timezone, timedelta

from bson import ObjectId

from .BaseDataModel import BaseDataModel
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.asynchronous.collection import AsyncCollection

from .db_schemas import Asset

from src.models.enums import DataBaseEnum, IndexStatusEnum


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
        asset_project_id: str,
        asset_type: str = None,
    ):
        query = {
            "asset_project_id": (
                ObjectId(asset_project_id)
                if isinstance(asset_project_id, str)
                else asset_project_id
            ),
        }

        if asset_type is not None:
            query["asset_type"] = asset_type

        records = await self.collection.find(query).to_list(length=None)

        return [Asset(**record) for record in records]

    async def get_asset_record(
        self,
        asset_project_id: str,
        asset_name: str,
    ):
        query = {
            "asset_project_id": (
                ObjectId(asset_project_id)
                if isinstance(asset_project_id, str)
                else asset_project_id
            ),
            "asset_name": asset_name,
        }

        record = await self.collection.find_one(query)

        if record:
            return Asset(**record)

        return None

    async def get_asset_by_id(
        self,
        project_id: ObjectId,
        asset_id: ObjectId,
    ) -> Asset | None:

        record = await self.collection.find_one(
            {
                "_id": asset_id,
                "asset_project_id": project_id,
            }
        )

        return Asset(**record) if record else None

    async def mark_indexed(
        self, asset_id: ObjectId, collection: str, chunks: int
    ) -> None:
        await self._set_index_state(
            asset_id,
            {
                "asset_index_status": IndexStatusEnum.INDEXED.value,
                "asset_index_collection": collection,
                "asset_indexed_chunks": chunks,
                "asset_indexed_at": datetime.now(timezone.utc),
                "asset_index_error": None,
            },
        )

    async def mark_failed(self, asset_id: ObjectId, error: str) -> None:
        await self._set_index_state(
            asset_id,
            {
                "asset_index_status": IndexStatusEnum.FAILED.value,
                "asset_index_error": error[
                    :500
                ],  # cap: never store huge tracebacks in a document
            },
        )

    async def mark_pending(self, asset_id: ObjectId) -> None:
        """Call after (re)processing a file: its chunks changed, so its vectors are stale."""
        await self._set_index_state(
            asset_id,
            {
                "asset_index_status": IndexStatusEnum.PENDING.value,
                "asset_indexed_chunks": 0,
            },
        )

    async def _set_index_state(self, asset_id: ObjectId, fields: dict) -> None:
        await self.collection.update_one(
            {"_id": asset_id},
            {"$set": fields},
        )

    async def try_claim_indexing(
        self,
        asset_id: ObjectId,
        collection: str,
        stale_after: timedelta = timedelta(minutes=30),
    ) -> bool:
        """
        Atomically move the asset to INDEXING. False = another run holds a live claim.
        """
        now = datetime.now(timezone.utc)
        result = await self.collection.update_one(
            {
                "_id": asset_id,
                "$or": [
                    {"asset_index_status": {"$ne": IndexStatusEnum.INDEXING.value}},
                    {
                        "asset_index_started_at": {"$lt": now - stale_after}
                    },  # crashed run
                ],
            },
            {
                "$set": {
                    "asset_index_status": IndexStatusEnum.INDEXING.value,
                    "asset_index_collection": collection,
                    "asset_index_started_at": now,
                    "asset_index_error": None,
                }
            },
        )

        return result.matched_count == 1

    async def get_index_summary(self, project_id: ObjectId) -> dict[str, dict]:
        """Count assets and indexed chunks per status, computed in Mongo (one round trip)."""
        cursor = await self.collection.aggregate(
            [
                {"$match": {"asset_project_id": project_id}},
                {
                    "$group": {
                        "_id": "$asset_index_status",
                        "assets": {"$sum": 1},
                        "chunks": {"$sum": "$asset_indexed_chunks"},
                    }
                },
            ]
        )
        rows = await cursor.to_list()
        # assets created before 4a have no status field -> they are pending
        return {
            (row["_id"] or IndexStatusEnum.PENDING.value): {
                "assets": row["assets"],
                "chunks": row["chunks"],
            }
            for row in rows
        }

    async def get_failed_assets(
        self, project_id: ObjectId, limit: int = 20
    ) -> list[Asset]:
        records = (
            await self.collection.find(
                {
                    "asset_project_id": project_id,
                    "asset_index_status": IndexStatusEnum.FAILED.value,
                }
            )
            .limit(limit)
            .to_list(length=limit)
        )

        return [Asset(**r) for r in records]

    async def get_asset_by_names(
        self, project_id: ObjectId, names: list[str]
    ) -> list[Asset]:
        records = await self.collection.find(
            {"asset_project_id": project_id, "asset_name": {"$in": names}}
        ).to_list(length=len(names))
        return [Asset(**r) for r in records]
