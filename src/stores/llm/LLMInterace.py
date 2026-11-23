from ..AsyncResource import AsyncResource

from abc import ABC, abstractmethod
from typing import AsyncIterator
from .LLMEnums import DocumentType, MessageRole


class GenerationProvider(AsyncResource):

    @abstractmethod
    def set_generation_model(self, model_id: str) -> None: ...

    @abstractmethod
    async def generate_text(
        self,
        prompt: str,
        chat_history: list[dict] | None = None,
        max_output_tokens: int | None = None,
        temperature: float | None = None,
    ) -> str: ...

    @abstractmethod
    def construct_prompt(
        self,
        prompt: str,
        role: MessageRole,
    ) -> dict: ...

    @abstractmethod
    def stream_text(
        self,
        prompt: str,
        chat_history: list[dict] | None = None,
        max_output_tokens: int | None = None,
        temperature: float | None = None,
    ) -> AsyncIterator[str]: ...


class EmbeddingProvider(AsyncResource):

    @abstractmethod
    def set_embedding_model(
        self,
        model_id: str,
        embedding_size: int,
    ) -> None: ...

    @abstractmethod
    async def embed_text(
        self,
        texts: list[str],
        document_type: DocumentType = DocumentType.DOCUMENT,
    ) -> list[list[float]]: ...
