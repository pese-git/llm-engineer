# Сначала импортируем модули без зависимостей
from sgr import AskAgent, UseTool, Reply, Finish, AgentStep, BusMessage
import traceback
import time
import sys
import json
import difflib
import os
from io import StringIO
from log import Log
from typing import Any, Dict, List, Optional, Union
from dotenv import load_dotenv

# Загружаем переменные окружения из .env файла
load_dotenv()

# Проверяем, загрузился ли ключ OpenRouter
if "OPENROUTER_API_KEY" in os.environ:
    print(f"OpenRouter API ключ загружен: {os.environ['OPENROUTER_API_KEY'][:10]}...")
else:
    print("Внимание: OPENROUTER_API_KEY не найден в переменных окружения")

# Создаем базовые объекты
from bus import MessageBus
from workspace import Workspace
from tools import Tools

bus = MessageBus()
ws = Workspace()
tools = Tools(ws)

# Импортируем модули, требующие глобальные переменные
import agent
import orchestrator

# Устанавливаем глобальные переменные
agent.bus = bus
orchestrator.bus = bus
orchestrator.tools = tools
orchestrator.ws = ws

# Теперь можно импортировать зависимые классы
from agent import PlannerAgent, CoderAgent, TesterAgent, ReviewerAgent
from orchestrator import Orchestrator



# ---------------------------
# Demo scenario: implement fib and run tests
# ---------------------------
goal = "Реализовать функцию is_prime(n: int) -> bool, которая проверяет, является ли число простым."

# Отправляем четкую структурированную инструкцию для всех агентов
bus.send(BusMessage(sender="planner", recipient="broadcast",
                    content="Coder: используй инструмент use_tool/store_code для записи файла solution.py. Tester: используй generate_tests, затем run_tests. Reviewer: проведи lint и ревью кода."))

# Run orchestrator с порядком, начиная с тестировщика
orch = Orchestrator()
orch.run(goal, order=["planner", "coder", "tester", "reviewer"], max_rounds=2)

# After run, print workspace artifacts and last few messages
Log.info(f"\nWorkspace files: { list(ws.files.keys())}")
if "solution.py" in ws.files:
    Log.info("=== solution.py ===\n")
    Log.info(ws.files["solution.py"])
if "tests.py" in ws.files:
    Log.info("=== tests.py ===\n")
    Log.info(ws.files["tests.py"])
    
print("\nLast bus history (tail 8):")
for m in bus.history[-8:]:
    Log.info(f"  {m.sender} -> {m.recipient}: {str(m.content)[:200]}")
