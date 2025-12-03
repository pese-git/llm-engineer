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
    
    def decide(self, context: dict) -> dict:
        raise NotImplementedError

class PlannerAgent(BaseAgent):
    name = "planner"
    description = (
        "Планирует задачу, делит её на этапы, делегирует кодеру/тестеру/ревьюеру. "
        "Всегда первым выдаёт поручение кодеру — реализовать функцию is_prime(n: int) -> bool в solution.py через инструмент store_code."
    )
    tools: List[str] = []

    def decide(self, context: dict) -> dict:
        return AgentAction(
            action="message",
            recipient="coder",
            content=(
                "Реализуй функцию is_prime(n: int) -> bool в solution.py через инструмент store_code! "
                "Сохрани решение ТОЛЬКО в solution.py. Не завершай выполнение, пока не вызван store_code."
            ),
        ).dict()

class CoderAgent(BaseAgent):
    name = "coder"
    description = (
        "Пишет код для решения задачи. Всегда сохраняет его в solution.py через инструмент store_code. "
        "Может использовать инструменты read_code, lint_code, run_python. Любые другие имена файлов запрещены."
    )
    tools: List[str] = ["store_code", "read_code", "run_python", "lint_code"]

    def decide(self, context: dict) -> dict:
        # Пример авто-кода (stub)
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
        "Пишет и запускает юнит-тесты к решению. Сохраняет тесты через инструмент store_code в test_solution.py и запускает через run_tests."
    )
    tools: List[str] = ["store_code", "read_code", "run_tests"]

    def decide(self, context: dict) -> dict:
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

# Сборка всех агентов

def get_agents():
    return [
        PlannerAgent(),
        CoderAgent(),
        TesterAgent(),
        ReviewerAgent()
    ]
