from typing import Optional, List, Any
import json
from sgr import AskAgent, UseTool, Finish, AgentStep

class BaseAgent:
    name: str = ""
    description: str = ""
    tools: List[str] = []

    def __init__(self, llm=None):
        self.llm = llm

    def decide(self, context: dict) -> AgentStep:
        raise NotImplementedError


def ensure_keys(d, keys, agent_name="agent"):
    missing = [k for k in keys if k not in d]
    if missing:
        raise ValueError(f"{agent_name}: отсутствуют ключи {missing} в ответе LLM: {d}\nПример верного JSON: {{'action': ..., 'tool_name': ..., 'args': ...}} или аналогичные.")

def ensure_not_null(out, agent_name="agent"):
    if out is None:
        raise ValueError(f"{agent_name}: LLM ответил пустым результатом! Проверь prompt и лимит токенов.")
    if not (isinstance(out, dict) or isinstance(out, list)):
        raise ValueError(f"{agent_name}: LLM ответил не dict и не list: {out}")

class PlannerAgent(BaseAgent):
    name = "planner"
    description = (
        "Координирует всю мультиагентную работу; анализирует историю и решает, кому дальше отправить baton и с каким заданием. Может возвращать задачи на доработку."
    )
    tools: List[str] = []

    def decide(self, context: dict) -> AgentStep:
        if not self.llm:
            raise RuntimeError("LLM is required for this agent!")
        messages = [
            {
                "role": "system",
                "content": (
                    "Ты — PlannerAgent, менеджер мультиагентной системы. Твоя задача — после КАЖДОГО шага анализировать историю (history) и определять, кому и что делать дальше.\n"
                    "Ты всегда формируешь только ОДИН валидный JSON-ответ: либо {\"action\": \"ask_agent\", \"target\": <агент>, \"message\": <подробное задание>}, либо — если ВСЁ ГОТОВО — {\"action\": \"finish\", \"summary\": <кратко результат>}\n"
                    "ПРАВИЛА:\n"
                    "- Если результат РЕВЬЮЕРА — ok (Стиль в порядке/стиль кода в порядке), baton -> finish: action='finish', summary='Все проверки пройдены, пайплайн завершён.'\n"
                    "- Если результат ревьюера — ошибка стиля (issues/ошибка), baton -> coder, message='Стиль не пройден, исправь стиль.'\n"
                    "- Если результат run_tests — ok (status=ok, все тесты прошли), baton -> reviewer, message='Проверь стиль кода (lint_code)'.\n"
                    "- Если результат run_tests — ошибка (status!=ok), baton -> coder, message='Тесты не пройдены, доработай решение, затем сохрани и запусти тесты повторно.'\n"
                    "- Если последний шаг tester был успешно store_code (test_solution.py) — теперь baton -> tester, message='Выполни инструмент run_tests (solution.py, test_solution.py)' (не повторяй store_code подряд).\n"
                    "- Если последний шаг coder — store_code, baton -> tester, message='Сгенерируй юнит-тесты на solution.py, сохрани их как test_solution.py, без комментариев и markdown.'\n"
                    "- Baton всегда можешь вернуть любому агента при ошибке или для доработки.\n"
                    "- Message всегда четко: либо сохрани, либо запусти, либо исправь, либо заверши.\n"
                )
            },
            {
                "role": "user",
                "content": (
                    f"Задача: {context['task']}\nИстория действий: {context['history']}"
                )
            }
        ]
        out = self.llm.complete(messages=messages)
        if isinstance(out, str):
            out = json.loads(out)
        ensure_not_null(out, "PlannerAgent")
        # finish или ask_agent (выбираем по action)
        if out.get("action") == "finish":
            from sgr import Finish
            step = Finish(action="finish", summary=out.get("summary", "Готово"))
            return AgentStep(step=step)
        ensure_keys(out, ["action", "target", "message"], "PlannerAgent")
        step = AskAgent(**out)
        return AgentStep(step=step)

class CoderAgent(BaseAgent):
    name = "coder"
    description = (
        "Пишет код решения задачи. Сохраняет только через инструмент store_code. "
        "Может использовать read_code, lint_code, run_python."
    )
    tools: List[str] = ["store_code", "read_code", "run_python", "lint_code"]

    def decide(self, context: dict):
        if not self.llm:
            raise RuntimeError("LLM is required for this agent!")
        inst = "Реализуй is_prime."
        for msg in reversed(context.get("history", [])):
            if msg.get("recipient") == "coder" and msg.get("action") in ("ask_agent", "message"):
                inst = msg.get("content") or msg.get("message", inst)
                break
        messages = [
            {
                "role": "system",
                "content": (
                    "Ты CoderAgent. Ответ ВСЕГДА должен быть СТРОГО ОДНИМ JSON-объектом: {\"action\": \"use_tool\", \"tool_name\": \"store_code\", \"args\": {\"filename\": \"solution.py\", \"code\": \"<CODE>\"}}. "
                    "Никаких массивов, никаких других полей, только эти ключи!"
                )
            },
            {
                "role": "user",
                "content": f"{inst}\nЗадача: {context['task']}"
            }
        ]
        out = self.llm.complete(messages=messages)
        if isinstance(out, str):
            out = json.loads(out)
        ensure_not_null(out, "CoderAgent")
        ensure_keys(out, ["action", "tool_name", "args"], "CoderAgent:use_tool")
        return AgentStep(step=UseTool(**out))

class TesterAgent(BaseAgent):
    name = "tester"
    description = (
        "Пишет и запускает юнит-тесты к решению. Сохраняет тесты через store_code и запускает через run_tests."
    )
    tools: List[str] = ["store_code", "read_code", "run_tests"]

    def decide(self, context: dict):
        if not self.llm:
            raise RuntimeError("LLM is required for this agent!")
        # Детект задачи от PlannerAgent: если нужно запустить тесты — делаем run_tests
        last_message = ""
        history = context.get("history", [])
        # ищем последнее message для tester из истории
        for entry in reversed(history):
            if entry.get("recipient") == "tester":
                last_message = entry.get("content", "")
                break
        if any(key in last_message.lower() for key in ["run_tests", "запусти тест", "запусти тесты", "test_solution.py, чтобы убедиться", "выполни инструмент run_tests"]):
            return AgentStep(step=UseTool(action="use_tool", tool_name="run_tests", args={
                "filename": "solution.py",
                "test_file": "test_solution.py"
            }))
        # иначе стандартное поведение (генерация тестов)
        messages = [
            {
                "role": "system",
                "content": (
                    "Ты TesterAgent. Если тесты ещё не созданы (нет файла 'test_solution.py'), ответь СТРОГО ОДНИМ JSON-объектом: {\"action\": \"use_tool\", \"tool_name\": \"store_code\", \"args\": {\"filename\": \"test_solution.py\", \"code\": \"<TESTS>\"}}. "
                    "Если тесты уже созданы — обязательно вызови run_tests посредством: {\"action\": \"use_tool\", \"tool_name\": \"run_tests\", \"args\": {\"filename\": \"solution.py\", \"test_file\": \"test_solution.py\"}}. "
                    "Никаких массивов, никаких других полей, только эти ключи!"
                )
            },
            {
                "role": "user",
                "content": (
                    "Задача: %s" % context["task"]
                )
            }
        ]
        out = self.llm.complete(messages=messages)
        if isinstance(out, str):
            out = json.loads(out)
        ensure_not_null(out, "TesterAgent")
        ensure_keys(out, ["action", "tool_name", "args"], "TesterAgent:use_tool")
        return AgentStep(step=UseTool(**out))

class ReviewerAgent(BaseAgent):
    name = "reviewer"
    description = (
        "Проверяет стиль, качество и эффективность кода, использует только инструменты read_code, lint_code, summarize_text."
    )
    tools: List[str] = ["read_code", "lint_code", "summarize_text"]

    def decide(self, context: dict):
        if not self.llm:
            raise RuntimeError("LLM is required for this agent!")
        messages = [
            {
                "role": "system",
                "content": (
                    "Ты ReviewerAgent. Ответ ВСЕГДА должен быть СТРОГО ОДНИМ JSON-объектом: {\"action\": \"use_tool\", \"tool_name\": \"lint_code\", \"args\": {\"code\": \"<CODE_TO_CHECK>\"}}. "
                    "Никаких массивов, никаких других полей!"
                )
            },
            {
                "role": "user",
                "content": (
                    f"Проверь стиль решения в solution.py. Задача: {context['task']}"
                )
            }
        ]
        out = self.llm.complete(messages=messages)
        if isinstance(out, str):
            out = json.loads(out)
        ensure_not_null(out, "ReviewerAgent")
        ensure_keys(out, ["action", "tool_name", "args"], "ReviewerAgent:use_tool")
        return AgentStep(step=UseTool(**out))

def get_agents(llm=None):
    return [
        PlannerAgent(llm=llm),
        CoderAgent(llm=llm),
        TesterAgent(llm=llm),
        ReviewerAgent(llm=llm)
    ]
