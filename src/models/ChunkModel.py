from pymongo.asynchronous.database import AsyncDatabase
from pymongo.asynchronous.collection import AsyncCollection

from .BaseDataModel import BaseDataModel
from .db_schemas import DataChunk

from .enums import DataBaseEnum

from bson.objectid import ObjectId
from pymongo import ASCENDING, InsertOne

from collections.abc import AsyncIterator


class ChunkModel(BaseDataModel):
    def __init__(
        self,
        db: AsyncDatabase,
    ):
        super().__init__(db=db)
        self.collection: AsyncCollection = self.db[
            DataBaseEnum.COLLECTION_CHUNK_NAME.value
        ]

    @classmethod
    async def create_instance(cls, db: AsyncDatabase):
        instance = cls(db)
        await instance.init_collection()
        return instance

    async def init_collection(self):
        return await self.collection.create_indexes(DataChunk.INDEXES)

    async def insert_chunk(self, chunk: DataChunk):
        result = await self.collection.insert_one(
            chunk.model_dump(by_alias=True, exclude_unset=True)
        )
        chunk._id = result.inserted_id
        return chunk

    async def get_chunk(self, chunk_id: str):
        result = await self.collection.find_one(
            {
                "_id": ObjectId(chunk_id),
            }
        )

        if result is None:
            return None

        return DataChunk(**result)

    async def insert_many_chunks(
        self,
        chunks: list,
        batch_size: int = 100,
    ):
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i : i + batch_size]

            operations = [
                InsertOne(chunk.model_dump(by_alias=True, exclude_unset=True))
                for chunk in batch
            ]

            await self.collection.bulk_write(operations)

        return len(chunks)

    async def delete_chunks_by_project_id(self, project_id: ObjectId):
        query = {"chunk_project_id": project_id}

        result = await self.collection.delete_many(query)

        return result.deleted_count

    async def iter_asset_chunks(
        self,
        project_id: ObjectId,
        asset_id: ObjectId,
        page_size: int = 64,
    ) -> AsyncIterator[list[DataChunk]]:
        """
        Yield an asset's chunks page by page (keyset pagination on _id).
        Memory stays constant no matter how many chunks the asset has.
        """

        last_id: ObjectId | None = None
        while True:
            query = {"chunk_project_id": project_id, "chunk_asset_id": asset_id}
            if last_id is not None:
                query["_id"] = {"$gt": last_id}

            records = (
                await self.collection.find(query)
                .sort("_id", ASCENDING)
                .limit(page_size)
                .to_list(length=page_size)
            )

            if not records:
                return

            yield [DataChunk(**record) for record in records]
            last_id = records[-1]["_id"]

    async def count_asset_chunks(self, project_id: ObjectId, asset_id: ObjectId) -> int:
        return await self.collection.count_documents(
            {"chunk_project_id": project_id, "chunk_asset_id": asset_id}
        )

    async def delete_chunks_by_asset_id(
        self, project_id: ObjectId, asset_id: ObjectId
    ) -> int:
        result = await self.collection.delete_many(
            {"chunk_project_id": project_id, "chunk_asset_id": asset_id}
        )

        return result.deleted_count
