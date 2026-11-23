from src.stores.vectordb.VectorDBEnums import VectorDBProvider

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from functools import lru_cache

from src.stores.llm.LLMEnums import LLMProvider


class Settings(BaseSettings):

    APP_NAME: str
    APP_VERSION: str

    FILE_ALLOWED_TYPES: list
    FILE_MAX_SIZE: int

    FILE_DEFAULT_CHUNK_SIZE: int

    MONGO_URL: str
    MONGODB_DATABASE: str

    GENERATION_BACKEND: LLMProvider = LLMProvider.GROQ
    EMBEDDING_BACKEND: LLMProvider = LLMProvider.OLLAMA

    # Groq: generation
    GROQ_API_KEY: SecretStr
    GENERATION_MODEL_ID: str = "openai/gpt-oss-120b"
    INPUT_DEFAULT_MAX_CHARS: int = 10_000
    GENERATION_DEFAULT_MAX_TOKENS: int = 4096
    GENERATION_DEFAULT_TEMPERATURE: float = 0.1
    GENERATION_REASONING_EFFORT: str | None = "low"

    # Ollama: embeddings
    OLLAMA_HOST: str = "http://localhost:11434"
    EMBEDDING_MODEL_ID: str = "bge-m3"
    EMBEDDING_MODEL_SIZE: int = 1024
    EMBEDDING_MAX_CHARS: int = 8_000
    EMBEDDING_BATCH_SIZE: int = 32
    EMBEDDING_NUM_CTX: int = 8192

    # Vector store
    VECTOR_DB_BACKEND: VectorDBProvider = VectorDBProvider.QDRANT
    VECTOR_DB_COLLECTION_PREFIX: str = "chunks"

    # Qdrant
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_API_KEY: SecretStr | None = None
    QDRANT_TIMEOUT: int = 30
    QDRANT_UPSERT_BATCH_SIZE: int = 256

    model_config = SettingsConfigDict(env_file=".env")


@lru_cache
def get_settings() -> Settings:
    return Settings()
