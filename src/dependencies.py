from typing import Annotated

from fastapi import Depends, Request
from pymongo.asynchronous.database import AsyncDatabase

from src.helpers.config import Settings, get_settings
from src.stores.llm.LLMInterace import EmbeddingProvider, GenerationProvider
from src.stores.vectordb.VectorDBInterface import VectorStore


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
