from __future__ import annotations

from typing import TYPE_CHECKING

from .LLMEnums import LLMProvider
from .LLMInterace import GenerationProvider, EmbeddingProvider
from .providers.GroqProvider import GroqProvider
from .providers.OllamaProvider import OllamaProvider

if TYPE_CHECKING:  # seen by your IDE and type checker, never executed at runtime
    from src.helpers.config import Settings


class LLMProviderFactory:
    def __init__(self, settings: Settings):
        self.config = settings

    def create_generation_client(self) -> GenerationProvider:
        cf = self.config
        match cf.GENERATION_BACKEND:
            case LLMProvider.GROQ:
                client = GroqProvider(
                    api_key=cf.GROQ_API_KEY.get_secret_value(),
                    default_input_max_chars=cf.INPUT_DEFAULT_MAX_CHARS,
                    default_generation_max_output_tokens=cf.GENERATION_DEFAULT_MAX_TOKENS,
                    default_generation_temperature=cf.GENERATION_DEFAULT_TEMPERATURE,
                    reasoning_effort=cf.GENERATION_REASONING_EFFORT,
                )
            case _:
                raise ValueError(
                    f"Unsupported generation backend: {cf.GENERATION_BACKEND}"
                )

        client.set_generation_model(cf.GENERATION_MODEL_ID)
        return client

    def create_embedding_client(self) -> EmbeddingProvider:
        cf = self.config
        match cf.EMBEDDING_BACKEND:
            case LLMProvider.OLLAMA:
                client = OllamaProvider(
                    host=cf.OLLAMA_HOST,
                    embedding_max_chars=cf.EMBEDDING_MAX_CHARS,
                    embedding_batch_size=cf.EMBEDDING_BATCH_SIZE,
                    embedding_num_ctx=cf.EMBEDDING_NUM_CTX,
                )
            case _:
                raise ValueError(
                    f"Unsupported embedding backend: {cf.EMBEDDING_BACKEND}"
                )

        client.set_embedding_model(cf.EMBEDDING_MODEL_ID, cf.EMBEDDING_MODEL_SIZE)
        return client
