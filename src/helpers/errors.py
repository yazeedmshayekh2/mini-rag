import logging

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from src.models.enums import ResponseEnum
from src.stores.vectordb.VectorDBExceptions import (
    VectorStoreConnectionError,
    VectorStoreError,
)
from src.stores.llm.LLMExceptions import LLMProviderError, ProviderUnavailableError

logger = logging.getLogger(__name__)


def register_exception_hanlders(app: FastAPI) -> None:
    @app.exception_handler(VectorStoreError)  # also catches every subclass
    async def vector_store_error_hanlder(request: Request, exc: VectorStoreError):
        if isinstance(exc, VectorStoreConnectionError):
            logger.warning("Vector store unavailable on %s: %s", request.url.path, exc)
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={"signal": ResponseEnum.VECTORDB_UNAVAILABLE.value},
                headers={"Retry-After": "10"},
            )
        logger.error("Vector store error on %s", request.url.path, exc_info=exc)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"signal": ResponseEnum.VECTORDB_ERROR.value},
        )

    @app.exception_handler(LLMProviderError)
    async def llm_provider_error_handler(request: Request, exc: LLMProviderError):
        if isinstance(exc, ProviderUnavailableError):
            logger.warning("LLM provider unavailable on %s: %s", request.url.path, exc)
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={"signal": ResponseEnum.LLM_UNAVAILABLE.value},
                headers={"Retry-After": "10"},
            )
        logger.error("LLM provider error on %s", request.url.path, exc_info=exc)
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content={"signal": ResponseEnum.LLM_ERROR.value},
        )
