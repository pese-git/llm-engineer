from typing import Optional, List, Any
from pydantic import BaseModel, Field
import json

# Pydantic-схема сообщения между агентами и для инструментов
class AgentAction(BaseModel):
    action: str = Field(..., description="Action type: 'message', 'tool_call', or 'done'")
    recipient: str = Field(default=None, description="The next agent to receive control")
    content: str = Field(default=None, description="Message for the next agent")
    tool: str = Field(default=None, description="Which tool to call, if any")
    params: dict = Field(default=dict, description="Parameters for the tool", json_schema_extra={"additionalProperties": False})

    model_config = {
        "extra": "forbid",
        "json_schema_extra": {
            "required": ["action"],
            "additionalProperties": False
        }
    }

class BaseAgent:
    name: str = ""
    description: str = ""
    tools: List[str] = []

    def __init__(self, llm=None):
        self.llm = llm

    def decide(self, context: dict) -> dict:
        raise NotImplementedError

class PlannerAgent(BaseAgent):
    name = "planner"
    description = (
        "Планирует задачу и делегирует первым шагом кодеру."
    )
    tools: List[str] = []

    def decide(self, context: dict) -> dict:
        if not self.llm:
            raise RuntimeError("LLM is required for this agent!")
        messages = [
            {
                "role": "system",
                "content": (
                    "Ты профессиональный 'PlannerAgent' мультиагентной системы. "
                    "Твоя роль — выдавать только валидные JSON-инструкции для менеджера и кодера."
                )
            },
            {
                "role": "user",
                "content": (
                    f"Task: {context['task']}\nИстория: {context['history']}\n"
                    "Ответь СТРОГО одним JSON-объектом формата: "
                    '{"action": "message", "recipient": "coder", "content": "Реализуй функцию is_prime(n: int) -> bool в solution.py через инструмент store_code! Сохрани решение ТОЛЬКО в solution.py. Не завершай выполнение, пока не вызван store_code."}'
                )
            }
        ]
        return self.llm.complete(messages=messages, schema=AgentAction)

class CoderAgent(BaseAgent):
    name = "coder"
    description = (
        "Пишет код решения задачи. Сохраняет только через инструмент store_code. "
        "Может использовать read_code, lint_code, run_python."
    )
    tools: List[str] = ["store_code", "read_code", "run_python", "lint_code"]

    def decide(self, context: dict) -> dict:
        if not self.llm:
            raise RuntimeError("LLM is required for this agent!")
        instructions = []
        for msg in reversed(context.get("history", [])):
            if msg["to"] == "coder" and msg["action"] == "message":
                instructions.append(msg["content"])
                break
        inst = instructions[0] if instructions else "Реализуй is_prime."
        messages = [
            {
                "role": "system",
                "content": (
                    "Ты исполняешь роль CoderAgent. Ты строго действуешь по JSON-инструкциям Planner или тестировщика."
                    "Всегда выдавай ответ только в формате JSON для менеджера."
                )
            },
            {
                "role": "user",
                "content": (
                    f"{inst}\n"
                    "Ответь СТРОГО JSON-структурой: "
                    '{"action": "tool_call", "tool": "store_code", "params": {"filename": "solution.py", "code": "<CODE>"}, "recipient": "tester", "content": "Код загружен через store_code. Пора тестировать!"}'
                    ' Где <CODE> — только рабочий код функции is_prime на Python (без markdown и комментариев).'
                )
            }
        ]
        return self.llm.complete(messages=messages, schema=AgentAction)

class TesterAgent(BaseAgent):
    name = "tester"
    description = (
        "Пишет и запускает юнит-тесты к решению. Сохраняет тесты через store_code и запускает через run_tests."
    )
    tools: List[str] = ["store_code", "read_code", "run_tests"]

    def decide(self, context: dict) -> dict:
        if not self.llm:
            raise RuntimeError("LLM is required for this agent!")
        messages = [
            {
                "role": "system",
                "content": (
                    "Ты TesterAgent. Сейчас твоя задача — написать минимальные юнит-тесты для проверки решения is_prime. "
                    "Ты должен обязательно CТРОГО возвращать JSON-структуру action/tool_call/params/recipient/content."
                )
            },
            {
                "role": "user",
                "content": (
                    """
Важно! Сгенерируй юнит-тесты на Python к функции is_prime. Только без markdown, без комментариев. Возвращай только JSON той структуры, что указана ниже:
{"action": "tool_call", "tool": "store_code", "params": {"filename": "test_solution.py", "code": "<TESTS>"}, "recipient": "reviewer", "content": "Тесты сохранены через store_code ('test_solution.py'). Запусти ревью!"}
Где <TESTS> — это рабочие автотесты.
"""
                )
            }
        ]
        return self.llm.complete(messages=messages, schema=AgentAction)

class ReviewerAgent(BaseAgent):
    name = "reviewer"
    description = (
        "Проверяет стиль, качество и эффективность кода, использует только инструменты read_code, lint_code, summarize_text."
    )
    tools: List[str] = ["read_code", "lint_code", "summarize_text"]

    def decide(self, context: dict) -> dict:
        if not self.llm:
            raise RuntimeError("LLM is required for this agent!")
        messages = [
            {
                "role": "system",
                "content": (
                    "Ты ReviewerAgent для мультиагентной цепочки.\n"
                    "Всегда анализируй стиль кода через инструмент lint_code, который принимает СТРОГО только параметр code (никаких filename, file, text и других)!\n"
                    "Ответ всегда только в формате JSON: {'action': 'tool_call', 'tool': 'lint_code', 'params': {'code': <CODE_FOR_CHECK>}, ...}.\n"
                )
            },
            {
                "role": "user",
                "content": (
                    f"Задача: {context['task']} История: {context['history']}. Проверь стиль решения в solution.py, вызови lint_code. Ответ должен быть только одним валидным JSON action, параметр code ОБЯЗАТЕЛЕН!"
                )
            }
        ]
        return self.llm.complete(messages=messages, schema=AgentAction)

def get_agents(llm=None):
    return [
        PlannerAgent(llm=llm),
        CoderAgent(llm=llm),
        TesterAgent(llm=llm),
        ReviewerAgent(llm=llm)
    ]
