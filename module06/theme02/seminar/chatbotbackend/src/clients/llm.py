from typing import Any

from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam

from src.settings import APIModelConfig, Settings


def _get_client(model_config: APIModelConfig) -> AsyncOpenAI:
    return AsyncOpenAI(
        api_key=model_config.key,
        base_url=str(model_config.base_url),
        timeout=model_config.timeout,
        max_retries=model_config.max_retries,
    )


def get_llm_client(settings: Settings) -> AsyncOpenAI:
    return _get_client(settings.llm)


def get_embedder_client(settings: Settings) -> AsyncOpenAI:
    return _get_client(settings.embedder)


async def get_chat_completion(
    user_query: str,
    system_message: str,
    settings: Settings,
    llm_client: AsyncOpenAI | None = None,
    params: dict[str, Any] | None = None,
    history: list[ChatCompletionMessageParam] | None = None,
) -> str:
    if llm_client is None:
        llm_client = get_llm_client(settings)
    response = await llm_client.chat.completions.create(
        model=settings.llm.name,
        messages=[
            {"role": "system", "content": system_message},
            *(history or []),
            {"role": "user", "content": user_query},
        ],
        **(params or {}),
    )
    return response.choices[0].message.content


async def get_embedding(
    text: str | list[str],
    settings: Settings,
    embedder_client: AsyncOpenAI | None = None,
) -> list[list[float]]:
    if embedder_client is None:
        embedder_client = get_embedder_client(settings)

    response = await embedder_client.embeddings.create(
        model=settings.embedder.name,
        input=text,
    )
    return [data.embedding for data in response.data]
