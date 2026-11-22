from contextlib import asynccontextmanager
from fastapi import FastAPI
from pymongo import AsyncMongoClient

from src.stores.llm import LLMProviderFactory

from .routes import base_router, data_router
from .helpers.config import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()

    # 1. Initialize client and database
    app.mongo_client = AsyncMongoClient(settings.MONGO_URL)
    app.db = app.mongo_client[settings.MONGODB_DATABASE]

    # 2. Use the exact same attribute name ('mongo_client')
    await app.mongo_client.admin.command("ping")

    factory = LLMProviderFactory(settings=settings)
    app.generation_client = factory.create_generation_client()
    app.embedding_client = factory.create_embedding_client()

    yield

    # 3. Close the same client reference on shutdown
    await app.mongo_client.close()


app = FastAPI(lifespan=lifespan)

app.include_router(base_router)
app.include_router(data_router)
