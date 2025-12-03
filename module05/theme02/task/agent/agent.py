# ---------------------------
# Базовый агент и конкретные агенты
# ---------------------------
from typing import Any, Dict, List, Optional, Union
from sgr import AskAgent, UseTool, Reply, Finish, AgentStep, BusMessage
from log import Log
from bus import MessageBus
from llm import call_llm_with_schema

# Переменная bus должна быть определена в main.py и передана сюда
# Этот импорт будет заполнен в runtime
bus = None

class AgentBase:
    """
    Базовый класс агента.

    Предназначен для всех агентов мультиагентной системы (planner, coder, tester, reviewer). 
    Содержит логику формирования запроса к LLM, обработки входящих сообщений и выбора действия.

    Атрибуты:
    ----------
    name : str
        Уникальное имя агента (например, "coder").

    system_role : str
        Описание роли агента, используется при формировании системного промпта для LLM.

    allowed_tools : List[str]
        Список инструментов (tool_name), которыми агент может пользоваться.
        Например: ["store_code", "read_code", "run_python"].

    Методы:
    --------
    decide(goal: str, inbox: List[BusMessage]) -> AgentStep
        Определяет действие агента на основе текущей цели и входящих сообщений.
        Возвращает экземпляр AgentStep, строго соответствующий Pydantic-схеме.
    """

    def __init__(self, name: str, system_role: str, allowed_tools: List[str]):
        self.name = name
        self.system_role = system_role
        self.allowed_tools = allowed_tools

    def decide(self, goal: str, inbox: List[BusMessage]) -> AgentStep:
        """
        Принимает решение о следующем действии агента.

        Параметры:
        -----------
        goal : str
            Текущая цель или задача, которую агент должен решить.
        inbox : List[BusMessage]
            Список сообщений, адресованных агенту. Используется для анализа последних
            взаимодействий и контекста.

        Логика:
        -------
        1. Формируется текстовый prompt для LLM, включающий:
            - роль агента и системное описание
            - текущую цель
            - последние сообщения (inbox)
            - история последних 20 сообщений в шине
            - список доступных инструментов

        2. Вызов LLM через call_llm_with_schema, с валидацией результата через Pydantic.

        3. Если LLM возвращает некорректный JSON или выбрасывает ошибку:
            - логируется ошибка
            - возвращается объект AgentStep с действием reply, информирующий
              о проблеме (fallback для безопасности).

        Возвращает:
        -----------
        AgentStep
            Экземпляр Pydantic-модели, описывающий выбранное действие:
            - AskAgent (задать вопрос другому агенту)
            - UseTool (вызвать инструмент из allowed_tools)
            - Reply (простое сообщение в шину)
            - Finish (сообщение о завершении задачи)
        """
        hist = "\n".join([f"{m.sender}->{m.recipient}: {m.content}" for m in bus.history[-20:]])
        inbox_text = "\n".join([f"{m.sender}: {m.content}" for m in inbox[-10:]])
        allowed = ", ".join(self.allowed_tools) or "(none)"
        
        # Подбираем специфичные инструкции для разных типов агентов
        agent_specific_instructions = ""
        if self.name == "tester":
            agent_specific_instructions = """
ВНИМАНИЕ ТЕСТИРОВЩИКУ: Вы должны строго следовать последовательности:
1. Сначала прочитать код решения через read_code
2. Затем создать тесты через store_code с параметром filename='tests.py'
3. Обязательно запустить тесты через run_tests с параметрами filename='solution.py', test_file='tests.py'

Если в ваших входящих сообщениях есть указание "создай tests.py", обязательно используйте инструмент store_code!
Если в ваших входящих сообщениях есть указание "запусти тесты", обязательно используйте инструмент run_tests!
"""

        prompt = f"""
Вы — {self.system_role} (имя агента: {self.name}).
Цель: {goal}

Входящие сообщения (последние):
{inbox_text}

История действий (последние):
{hist}

{agent_specific_instructions}

ДОСТУПНЫЕ ВАМ ИНСТРУМЕНТЫ:
{allowed}

ВАЖНО:
- При вызове инструмента store_code вы ОБЯЗАТЕЛЬНО должны заполнять оба аргумента в args: filename (например, 'solution.py') И code (строкой с кодом). Нельзя отправлять пустой или отсутствующий код!
- При других инструментах (например, run_python) тоже заполняйте необходимые поля по их описанию.

Вы должны выбрать ТОЛЬКО одно действие и вернуть JSON строго в соответствии со схемой:
AgentStep -> step: одно из ask_agent/use_tool/reply/finish.

- ask_agent: target в ['planner','coder','tester','reviewer'], message — сообщение
- use_tool: tool_name (должно быть одним из доступных вам инструментов), args (dict) — аргументы инструмента
- reply: content (строка) — ответ
- finish: summary (строка) — итоговое сообщение

ВАЖНО: Если вы тестировщик и видите, что вам нужно создать тесты, используйте store_code с filename='tests.py', 
а затем обязательно используйте run_tests для запуска тестов.

Возвращайте ТОЛЬКО JSON. Никаких объяснений.
"""
        try:
            resp = call_llm_with_schema(prompt, AgentStep, system_prompt=self.system_role)
            return resp
        except Exception as e:
            Log.error(f"[{self.name}] LLM failed to produce valid AgentStep: {e}")
            step = {"step": {"action": "reply", "content": f"Error generating action: {str(e)[:200]}" }}
            return AgentStep.model_validate(step)


# ---------------------------
# Конкретные агенты
# ---------------------------

class PlannerAgent(AgentBase):
    """
    Агент планирования (planner).

    Задачи:
    -------
    - Определяет задачи и цели для других агентов.
    - Распределяет роли и инструменты.
    - Не использует инструменты Workspace напрямую.
    """
    def __init__(self):
        super().__init__("planner", "Planner: определяет задачи и назначает роли.", allowed_tools=[])


class CoderAgent(AgentBase):
    """
    Агент-программист (coder).

    Задачи:
    -------
    - Реализует функции и решения задачи.
    - Использует инструменты Workspace: store_code, read_code, run_python, lint_code.
    """
    def __init__(self):
        super().__init__(
            "coder",
            "Coder: реализует код с использованием инструментов рабочей среды.",
            allowed_tools=["store_code", "read_code", "run_python", "lint_code"]
        )


class TesterAgent(AgentBase):
    """
    Агент-тестировщик (tester).

    Задачи:
    -------
    - Генерирует и запускает тесты.
    - Анализирует код решения и требования задачи для создания релевантных тестов.
    - Использует инструменты Workspace: read_code, run_tests, store_code.
    
    Процесс работы:
    ---------------
    1. Читает код решения с помощью read_code
    2. Генерирует подходящие тесты с помощью LLM на основе анализа кода
    3. Сохраняет тесты в файл с помощью store_code 
    4. Запускает тесты с помощью run_tests с параметром test_file
    
    Структура последовательности действий:
    ------------------------------------
    ШАГ 1: read_code → Прочитать файл с решением
    ШАГ 2: store_code → Создать файл с тестами
    ШАГ 3: run_tests → Запустить тесты
    """
    def __init__(self):
        super().__init__(
            "tester",
            "Tester: Генерирует и выполняет тесты, анализируя код решения и требования задачи. ОБЯЗАТЕЛЬНО следует протоколу: 1) read_code, 2) store_code, 3) run_tests.",
            allowed_tools=["read_code", "run_tests", "store_code"]
        )


class ReviewerAgent(AgentBase):
    """
    Агент-рецензент (reviewer).

    Задачи:
    -------
    - Проверяет качество кода, соблюдение стиля и best practices.
    - Может делать рекомендации и запросы на исправление.
    - Использует инструменты Workspace: read_code, lint_code, summarize_text.
    """
    def __init__(self):
        super().__init__(
            "reviewer",
            "Reviewer: Проверяет качество кода и запрашивает исправления.",
            allowed_tools=["read_code", "lint_code", "summarize_text"]
        )
