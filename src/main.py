from contextlib import asynccontextmanager
from fastapi import FastAPI
from pymongo import AsyncMongoClient

from .routes import base_router, data_router
from .helpers.config import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI):

    settings = get_settings()
    app.mongo_conn = AsyncMongoClient(settings.MONGO_URL)
    app.db_client = app.mongo_db[settings.MONGODB_DATABASE]

    await app.mongo_conn.admin.command("ping")

    yield

    await app.mongo_conn.close()


app = FastAPI(lifespan=lifespan)

app.include_router(base_router)
app.include_router(data_router)
