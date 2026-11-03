from fastapi import FastAPI, APIRouter
import os

APP_NAME = os.getenv("APP_NAME")
APP_VERSION = os.getenv("APP_VERSION")

base_router = APIRouter(
    prefix="/api/v1",
    tags=["api_v1"],
)


@base_router.get("/")
def welcome():
    return {
        "App Name": f"{APP_NAME}",
        "App Version": f"{APP_VERSION}",
    }
