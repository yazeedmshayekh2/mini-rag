class LLMProviderError(Exception):
    """Base class: callers catch this for any embedding/generation provider failure."""


class ProviderUnavailableError(LLMProviderError):
    """Provider unreachable, timed out, or rate-limited: retrying later may work."""


class ProviderResponseError(LLMProviderError):
    """Provider answered with an error: bad request, missing model, auth. Retrying won't help."""
