import logging
from contextlib import AsyncExitStack, asynccontextmanager

from fastapi import FastAPI
from pymongo import AsyncMongoClient

from .helpers.config import get_settings
from .routes import base_router, data_router, nlp_router
from .stores.llm.LLMProviderFactory import LLMProviderFactory
from .stores.vectordb.VectorDBProviderFactory import VectorDBProviderFactory
from .stores.vectordb.collections import chunks_collection_spec

from .helpers.errors import register_exception_hanlders
from .models import ProjectModel, AssetModel, ChunkModel

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

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

        for model_cls in (ProjectModel, AssetModel, ChunkModel):
            await model_cls(app.state.db).init_collection()

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
register_exception_hanlders(app=app)
app.include_router(base_router)
app.include_router(data_router)
app.include_router(nlp_router)
