from pymongo.asynchronous.database import AsyncDatabase
from pymongo.asynchronous.collection import AsyncCollection

from .BaseDataModel import BaseDataModel
from .db_schemas import Project

from .enums import DataBaseEnum

import asyncio


class ProjectModel(BaseDataModel):
    def __init__(
        self,
        db: AsyncDatabase,
    ):
        super().__init__(db=db)
        self.collection: AsyncCollection = self.db[
            DataBaseEnum.COLLECTION_PROJECT_NAME.value
        ]

    async def create_project(
        self,
        project: Project,
    ):
        result = await self.collection.insert_one(
            project.model_dump(by_alias=True, exclude_unset=True)
        )
        project.id = result.inserted_id
        return project

    async def get_or_create_project(
        self,
        project_id: str,
    ):
        record = await self.collection.find_one(
            {
                "project_id": project_id,
            }
        )

        if record is None:
            project = Project(project_id=project_id)
            project = await self.create_project(project=project)

            return project

        return Project(**record)

    async def get_all_projects(
        self,
        page: int = 1,
        page_size: int = 10,
    ) -> tuple[list[Project], int]:

        total_documents, records = await asyncio.gather(
            self.collection.estimated_document_count(),
            self.collection.find()
            .sort("_id", 1)
            .skip((page - 1) * page_size)
            .limit(page_size)
            .to_list(length=page_size),
        )

        projects = [Project(**record) for record in records]
        total_pages = (total_documents + page_size - 1) // page_size

        return projects, total_pages
