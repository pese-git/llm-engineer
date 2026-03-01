from typing import Annotated

from fastapi import Depends, FastAPI

from src.dependencies import get_settings
from src.pipeline.config import CHAT_BOT
from src.pipeline.context import Context
from src.pipeline.orchestrator import Orchestrator
from src.schemes import ChatRequest
from src.settings import Settings

app = FastAPI(
    title="LLM Service API",
    description="API for interacting with Large Language Models",
)


@app.get("/health")
async def health_check():
    return {"status": "ok"}


@app.post("/chat")
async def chat(
    request: ChatRequest,
    settings: Annotated[Settings, Depends(get_settings)],
) -> str:
    orchestrator = Orchestrator(CHAT_BOT)
    context = Context(
        query=request.query,
        history=request.history or [],
        settings=settings,
    )
    return await orchestrator.execute(context)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8080)
