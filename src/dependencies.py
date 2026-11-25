from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from pymongo.asynchronous.database import AsyncDatabase

from src.helpers.config import Settings, get_settings
from src.models import ProjectModel, AssetModel, ChunkModel
from src.models.db_schemas import Project
from src.models.enums import ResponseEnum
from src.services.IndexingService import IndexingService
from src.stores.llm.LLMInterace import EmbeddingProvider, GenerationProvider
from src.stores.vectordb.VectorDBInterface import VectorStore


# ---------- app-scoped singletons (created once in lifespan) ----------
def get_db(request: Request) -> AsyncDatabase:
    return request.app.state.db


def get_vector_store(request: Request) -> VectorStore:
    return request.app.state.vector_store


def get_chunks_collection(request: Request) -> str:
    return request.app.state.chunks_collection


def get_embedding_client(request: Request) -> EmbeddingProvider:
    return request.app.state.embedding_client


def get_generation_client(request: Request) -> GenerationProvider:
    return request.app.state.generation_client


# Short aliases for route signatures
SettingsDep = Annotated[Settings, Depends(get_settings)]
DbDep = Annotated[AsyncDatabase, Depends(get_db)]
VectorStoreDep = Annotated[VectorStore, Depends(get_vector_store)]
ChunksCollectionDep = Annotated[str, Depends(get_chunks_collection)]
EmbeddingDep = Annotated[EmbeddingProvider, Depends(get_embedding_client)]
GenerationDep = Annotated[GenerationProvider, Depends(get_generation_client)]


# ---------- per-request lookups ----------
async def get_project(project_id: str, db: DbDep) -> Project:
    """Resolve the public project_id from the path; 404 instead of creating it."""
    project = await ProjectModel(db=db).get_project_by_public_id(project_id=project_id)
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"signal": ResponseEnum.PROJECT_NOT_FOUND.value},
        )
    return project


ProjectDep = Annotated[Project, Depends(get_project)]


# ---------- services (the composition point) ----------
def get_indexing_service(
    db: DbDep,
    embedder: EmbeddingDep,
    vector_store: VectorStoreDep,
    collection: ChunksCollectionDep,
    settings: SettingsDep,
) -> IndexingService:
    return IndexingService(
        chunk_model=ChunkModel(db),
        asset_model=AssetModel(db),
        embedder=embedder,
        vector_store=vector_store,
        collection=collection,
        page_size=settings.INDEXING_PAGE_SIZE,
    )


IndexingServiceDep = Annotated[IndexingService, Depends(get_indexing_service)]
