from typing import Any

from langfuse._client.get_client import get_client
from openai import AsyncOpenAI
from qdrant_client import AsyncQdrantClient

from src.clients.llm import get_embedder_client, get_embedding
from src.settings import Settings


def get_qdrant_client(
    settings: Settings,
) -> AsyncQdrantClient:
    return AsyncQdrantClient(
        location=str(settings.qdrant_host),
    )


async def get_documents(
    query: str,
    settings: Settings,
    top_k: int = 5,
    params: dict[str, Any] | None = None,
    qdrant_client: AsyncQdrantClient | None = None,
    embedder_client: AsyncOpenAI | None = None,
) -> list[str]:
    if qdrant_client is None:
        qdrant_client = get_qdrant_client(settings)
    if embedder_client is None:
        embedder_client = get_embedder_client(settings)

    with get_client().start_as_current_observation(
        as_type="retriever",
        name="qdrant-retrieval",
        input={"input": query, "top_k": top_k, **(params or {})},
    ) as observation:
        embedding = await get_embedding(
            text=query,
            embedder_client=embedder_client,
            settings=settings,
        )
        query_response = await qdrant_client.query_points(
            collection_name=settings.qdrant_collection,
            query=embedding[0],
            limit=top_k,
        )
        observation.update(
            output=query_response.model_dump(),
        )
    return [rec.payload["text"] for rec in query_response.points]
