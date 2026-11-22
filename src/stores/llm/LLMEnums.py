from enum import Enum


class LLMProvider(str, Enum):
    GROQ = "GROQ"
    OLLAMA = "OLLAMA"


class MessageRole(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


class DocumentType(str, Enum):
    DOCUMENT = "document"  # chunks being indexed
    QUERY = "query"  # the user's question at search time
