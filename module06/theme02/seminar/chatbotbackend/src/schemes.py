from openai.types.chat import (
    ChatCompletionAssistantMessageParam,
    ChatCompletionUserMessageParam,
)
from pydantic import BaseModel


class ChatRequest(BaseModel):
    query: str
    history: (
        list[ChatCompletionUserMessageParam | ChatCompletionAssistantMessageParam]
        | None
    ) = None
