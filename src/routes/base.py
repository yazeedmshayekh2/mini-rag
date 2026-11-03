from fastapi import FastAPI, APIRouter
from ..helpers.config import get_settings

app_settings = get_settings()

base_router = APIRouter(
    prefix="/api/v1",
    tags=["api_v1"],
)


@base_router.get("/")
def welcome():

    app_name = app_settings.APP_NAME
    app_version = app_settings.APP_VERSION

    return {
        "app_name": f"{app_name}",
        "app_version": f"{app_version}",
    }
