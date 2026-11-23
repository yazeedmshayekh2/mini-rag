import logging
from contextlib import AsyncExitStack, asynccontextmanager

from fastapi import FastAPI
from pymongo import AsyncMongoClient

from .helpers.config import get_settings
from .routes import base_router, data_router
from .stores.llm.LLMProviderFactory import LLMProviderFactory
from .stores.vectordb.VectorDBProviderFactory import VectorDBProviderFactory
from .stores.vectordb.collections import chunks_collection_spec

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()

    async with (
        AsyncExitStack() as stack
    ):  # cleanups run in reverse order, even if startup fails
        # 1. MongoDB: source of truth
        mongo_client = AsyncMongoClient(settings.MONGO_URL)
        stack.push_async_callback(mongo_client.close)
        await mongo_client.admin.command("ping")
        app.state.mongo_client = mongo_client
        app.state.db = mongo_client[settings.MONGODB_DATABASE]

        # 2. LLM providers
        llm_factory = LLMProviderFactory(settings=settings)

        generation_client = llm_factory.create_generation_client()
        stack.push_async_callback(generation_client.close)
        app.state.generation_client = generation_client

        embedding_client = llm_factory.create_embedding_client()
        stack.push_async_callback(embedding_client.close)
        app.state.embedding_client = embedding_client

        # 3. Vector store: derived index
        vector_store = VectorDBProviderFactory(settings=settings).create()
        await stack.enter_async_context(
            vector_store
        )  # connect() now, close() on shutdown
        spec = chunks_collection_spec(
            settings.VECTOR_DB_COLLECTION_PREFIX,
            settings.EMBEDDING_MODEL_ID,
            settings.EMBEDDING_MODEL_SIZE,
        )
        await vector_store.ensure_collection(spec)  # fails fast on size/metric mismatch
        app.state.vector_store = vector_store
        app.state.chunks_collection = spec.name

        logger.info("Startup complete: collection '%s'", spec.name)
        yield
    # leaving the stack: vector store closed, then Mongo closed


app = FastAPI(lifespan=lifespan)
app.include_router(base_router)
app.include_router(data_router)
