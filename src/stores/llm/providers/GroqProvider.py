import asyncio
import logging
from typing import AsyncIterator
from groq import AsyncGroq

from ..LLMInterace import GenerationProvider
from ..LLMEnums import MessageRole

logger = logging.getLogger(__name__)


class GroqProvider(GenerationProvider):
    def __init__(
        self,
        api_key: str,
        default_input_max_chars: int = 10_000,
        default_generation_max_output_tokens: int = 4096,
        default_generation_temperature: float = 0.1,
        reasoning_effort: (
            str | None
        ) = "low",  # gpt-oss: low/medium/high, qwen: none/default, allam: None
        timeout: float = 60.0,
        max_retries: int = 2,
    ):
        self.client = AsyncGroq(
            api_key=api_key, timeout=timeout, max_retries=max_retries
        )
        self.default_input_max_chars = default_input_max_chars
        self.default_generation_max_output_tokens = default_generation_max_output_tokens
        self.default_generation_temperature = default_generation_temperature
        self.reasoning_effort = reasoning_effort
        self.generation_model_id: str | None = None

        self._closed = False

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        await self.client.close()

    def set_generation_model(self, model_id: str) -> None:
        self.generation_model_id = model_id

    def _process_text(self, text: str) -> str:
        return text[: self.default_input_max_chars].strip()

    def construct_prompt(self, prompt: str, role: MessageRole) -> dict:
        return {"role": role.value, "content": self._process_text(prompt)}

    def _build_request(
        self, prompt, chat_history, max_output_tokens, temperature
    ) -> dict:
        if not self.generation_model_id:
            raise RuntimeError("Generation model is not set for GroqProvider")

        request = {
            "model": self.generation_model_id,
            "messages": [
                *(chat_history or []),
                self.construct_prompt(prompt=prompt, role=MessageRole.USER),
            ],
            "max_completion_tokens": max_output_tokens
            or self.default_generation_max_output_tokens,
            "temperature": (
                self.default_generation_temperature
                if temperature is None
                else temperature
            ),
        }

        if self.reasoning_effort:
            request["reasoning_effort"] = self.reasoning_effort

        return request

    async def generate_text(
        self, prompt, chat_history=None, max_output_tokens=None, temperature=None
    ) -> str:
        request = self._build_request(
            prompt, chat_history, max_output_tokens, temperature
        )
        response = await self.client.chat.completions.create(**request)
        if not response.choices:
            raise RuntimeError("Empty response from Groq")
        return response.choices[0].message.content

    async def stream_text(
        self, prompt, chat_history=None, max_output_tokens=None, temperature=None
    ) -> AsyncIterator[str]:
        request = self._build_request(
            prompt, chat_history, max_output_tokens, temperature
        )
        stream = await self.client.chat.completions.create(**request, stream=True)

        produced_text = False
        finish_reason = None
        try:
            async for chunk in stream:
                if not chunk.choices:
                    continue
                choice = chunk.choices[0]

                if choice.delta.content:  # skip role-only, reasoning and final chunks
                    produced_text = True
                    yield choice.delta.content

                if choice.finish_reason:
                    finish_reason = choice.finish_reason
        finally:
            await stream.close()  # release the connection, e.g. if the client disconnects

        if finish_reason == "length":
            logger.warning(
                "Groq stream hit max_completion_tokens=%s (model=%s)%s",
                request["max_completion_tokens"],
                self.generation_model_id,
                (
                    " before producing any text: reasoning used the whole budget"
                    if not produced_text
                    else ""
                ),
            )
        elif not produced_text:
            logger.warning("Groq stream finished (%s) without any text", finish_reason)


# async def main():
#     from ....helpers.config import get_settings

#     logging.basicConfig(level=logging.INFO)
#     settings = get_settings()

#     groq_provider = GroqProvider(
#         api_key=settings.GROQ_API_KEY.get_secret_value(),
#         default_generation_max_output_tokens=settings.GENERATION_DEFAULT_MAX_TOKENS,
#         default_generation_temperature=settings.GENERATION_DEFAULT_TEMPERATURE,
#         default_input_max_chars=settings.INPUT_DEFAULT_MAX_CHARS,
#     )
#     groq_provider.set_generation_model(model_id=settings.GENERATION_MODEL_ID)

#     async for token in groq_provider.stream_text(
#         "Could you please tell me about the KV cache and how does this could be reduced while inferencing using the vLLM PagedAttention method"
#     ):
#         print(token, end="", flush=True)
#     print()


# if __name__ == "__main__":
#     asyncio.run(main())
