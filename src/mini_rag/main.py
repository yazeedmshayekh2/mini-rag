from fastapi import FastAPI
from dotenv import load_dotenv

load_dotenv(".env")

from .routes import base_router

app = FastAPI()

app.include_router(base_router)
