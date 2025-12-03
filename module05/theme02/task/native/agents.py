from typing import List, Dict, Any
from pydantic import BaseModel

# Pydantic-схема сообщения между агентами и для инструментов
class AgentAction(BaseModel):
    action: str  # 'message', 'tool_call', 'done'
    recipient: str = None
    content: str = None
    tool: str = None
    params: Dict[str, Any] = {}

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
        if self.llm:
            prompt = (
                f"Задача: {context['task']}\nИстория:\n{context['history']}\n"
                "Сформулируй как раздать задачу кодеру/следующему агенту краткой технической инструкцией, строго по клише для автоматического исполнения, не давая финального ответа, а только следующую подзадачу для coder."
            )
            content = self.llm.complete(prompt)
        else:
            content = (
                "Реализуй функцию is_prime(n: int) -> bool в solution.py через инструмент store_code! "
                "Сохрани решение ТОЛЬКО в solution.py. Не завершай выполнение, пока не вызван store_code."
            )
        return AgentAction(
            action="message",
            recipient="coder",
            content=content,
        ).dict()

class CoderAgent(BaseAgent):
    name = "coder"
    description = (
        "Пишет код решения задачи. Сохраняет только через инструмент store_code. "
        "Может использовать read_code, lint_code, run_python."
    )
    tools: List[str] = ["store_code", "read_code", "run_python", "lint_code"]

    def decide(self, context: dict) -> dict:
        if self.llm:
            instructions = []
            for msg in reversed(context.get("history", [])):
                if msg["to"] == "coder" and msg["action"] == "message":
                    instructions.append(msg["content"])
                    break
            inst = instructions[0] if instructions else "Реализуй is_prime."
            prompt = (
                f"{inst}\nНапиши полный код в формате Python-функции, коротко. Только функцию."
            )
            code = self.llm.complete(prompt)
        else:
            code = (
                "def is_prime(n: int) -> bool:\n"
                "    if n < 2:\n        return False\n"
                "    for i in range(2, int(n ** 0.5) + 1):\n"
                "        if n % i == 0:\n            return False\n"
                "    return True"
            )

        return AgentAction(
            action="tool_call",
            tool="store_code",
            params={"filename": "solution.py", "code": code},
            recipient="tester",
            content="Код загружен через store_code. Пора тестировать!"
        ).dict()

class TesterAgent(BaseAgent):
    name = "tester"
    description = (
        "Пишет и запускает юнит-тесты к решению. Сохраняет тесты через store_code и запускает через run_tests."
    )
    tools: List[str] = ["store_code", "read_code", "run_tests"]

    def decide(self, context: dict) -> dict:
        if self.llm:
            prompt = (
                "Напиши краткие юнит-тесты в формате функций Python, проверяющих корректность is_prime."
            )
            tests = self.llm.complete(prompt)
        else:
            tests = (
                "def test_is_prime():\n"
                "    assert is_prime(2)\n    assert is_prime(7)\n    assert not is_prime(4)"
            )
        return AgentAction(
            action="tool_call",
            tool="store_code",
            params={"filename": "test_solution.py", "code": tests},
            recipient="reviewer",
            content="Тесты сохранены через store_code ('test_solution.py'). Запусти ревью!"
        ).dict()

class ReviewerAgent(BaseAgent):
    name = "reviewer"
    description = (
        "Проверяет стиль, качество и эффективность кода, использует только инструменты read_code, lint_code, summarize_text."
    )
    tools: List[str] = ["read_code", "lint_code", "summarize_text"]

    def decide(self, context: dict) -> dict:
        return AgentAction(
            action="tool_call",
            tool="lint_code",
            params={"code": "..."},
            recipient="manager",
            content="Стиль проверен. Горжусь!"
        ).dict()

def get_agents(llm=None):
    return [
        PlannerAgent(llm=llm),
        CoderAgent(llm=llm),
        TesterAgent(llm=llm),
        ReviewerAgent(llm=llm)
    ]
