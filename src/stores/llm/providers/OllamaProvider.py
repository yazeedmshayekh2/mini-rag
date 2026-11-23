import logging

from ollama import AsyncClient

from ..LLMInterace import EmbeddingProvider
from ..LLMEnums import DocumentType
from ..text_utils import normalize_for_embedding

logger = logging.getLogger(__name__)

EMBEDDING_PREFIXES: dict[str, dict[DocumentType, str]] = {
    "bge-m3": {},  # no prefixes
    "qwen3-embedding": {
        DocumentType.QUERY: "Instruct: Given a search query, retrieve relevant passages that answer the query\nQuery: ",
    },
    "embeddinggemma": {
        DocumentType.DOCUMENT: "title: none | text: ",
        DocumentType.QUERY: "task: search result | query: ",
    },
    "snowflake-arctic-embed2": {
        DocumentType.QUERY: "query: ",
    },
}


class OllamaProvider(EmbeddingProvider):
    def __init__(
        self,
        host: str = "http://localhost:11434",
        embedding_max_chars: int = 8_000,
        embedding_batch_size: int = 32,
        embedding_num_ctx: int = 8192,
        timeout: float = 120.0,
    ):
        self.client = AsyncClient(host=host, timeout=timeout)

        self.embedding_max_chars = embedding_max_chars
        self.embedding_batch_size = embedding_batch_size
        self.embedding_num_ctx = embedding_num_ctx

        self.embedding_model_id: str | None = None
        self.embedding_size: int | None = None

        self._closed = False

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        await self.client.close()

    def set_embedding_model(self, model_id: str, embedding_size: int) -> None:
        self.embedding_model_id = model_id
        self.embedding_size = embedding_size

    def _prefix(self, document_type: DocumentType) -> str:
        base_name = self.embedding_model_id.split(":")[0]  # "bge-m3:latest" -> "bge-m3"
        return EMBEDDING_PREFIXES.get(base_name, {}).get(document_type, "")

    def _prepare(self, text: str, document_type: DocumentType) -> str:
        text = normalize_for_embedding(text)[: self.embedding_max_chars]
        return self._prefix(document_type) + text

    async def embed_text(
        self,
        texts: list[str],
        document_type: DocumentType = DocumentType.DOCUMENT,
    ) -> list[list[float]]:
        if not self.embedding_model_id:
            raise RuntimeError("Embedding model is not set for OllamaProvider")
        if not texts:
            return []

        inputs = [self._prepare(t, document_type) for t in texts]
        vectors: list[list[float]] = []

        for start in range(0, len(inputs), self.embedding_batch_size):
            batch = inputs[start : start + self.embedding_batch_size]
            response = await self.client.embed(
                model=self.embedding_model_id,
                input=batch,
                options={"num_ctx": self.embedding_num_ctx},
            )
            if len(response.embeddings) != len(batch):
                raise RuntimeError(
                    f"Ollama returned {len(response.embeddings)} embeddings for {len(batch)} inputs"
                )
            vectors.extend(response.embeddings)

        if len(vectors[0]) != self.embedding_size:
            raise ValueError(
                f"Expected embedding size {self.embedding_size}, got {len(vectors[0])}. "
                "Check EMBEDDING_MODEL_SIZE matches the model."
            )

        logger.debug("Embedded %d texts with %s", len(vectors), self.embedding_model_id)
        return vectors
