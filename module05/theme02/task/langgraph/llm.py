import os
from langchain_openai import ChatOpenAI

def get_llm():
    """
    Универсальный LLM-инициализатор для LangGraph-агентов — поддерживает OpenAI, OpenRouter, Azure через переменные окружения.
    Добавлен response_format для строгого JSON-ответа.
    """
    return ChatOpenAI(
        api_key=os.environ.get("OPENAI_API_KEY"),
        base_url=os.environ.get("OPENAI_API_BASE"),
        model=os.environ.get("OPENAI_MODEL", "gpt-4o"),
        temperature=float(os.environ.get("OPENAI_TEMPERATURE", "0")),
        model_kwargs={
            "response_format": {"type": "json_object"}
        }
    )
