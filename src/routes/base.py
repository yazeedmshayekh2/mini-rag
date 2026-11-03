from fastapi import FastAPI, APIRouter
from ..helpers.config import get_settings

config = get_settings()

base_router = APIRouter(
    prefix="/api/v1",
    tags=["api_v1"],
)


@base_router.get("/")
def welcome():
    return {
        "app_name": f"{config.APP_NAME}",
        "app_version": f"{config.APP_VERSION}",
    }
