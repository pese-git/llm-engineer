# ---------------------------
# Оркестратор — управление агентами, контроль инструментов, логирование
# ---------------------------
from typing import Any, Dict, List, Optional
from sgr import AskAgent, UseTool, Reply, Finish, BusMessage
from log import Log
from bus import MessageBus
from agent import PlannerAgent, CoderAgent, TesterAgent, ReviewerAgent
import traceback

# Переменная bus должна быть определена в main.py и передана сюда
# Этот импорт будет заполнен в runtime
bus = None
tools = None  # Аналогично для инструментов

class Orchestrator:
    """
    Оркестратор мультиагентной системы.

    Основная роль:
    ---------------
    - Управляет последовательностью действий агентов.
    - Контролирует использование инструментов (tools) и проверяет права доступа.
    - Логирует действия, ошибки и результаты.
    - Обеспечивает маршрутизацию сообщений между агентами через MessageBus.
    - Реализует правила завершения задачи (Finish).

    Атрибуты:
    ----------
    agents : Dict[str, AgentBase]
        Словарь всех агентов системы с ключами по имени роли.
        Примеры ключей: "planner", "coder", "tester", "reviewer".

    allowed_tools : Dict[str, List[str]]
        Словарь соответствий роли → список разрешённых инструментов.

    max_rounds : int
        Максимальное количество раундов взаимодействия агентов.
    """

    def __init__(self):
        self.agents = {
            "planner": PlannerAgent(),
            "coder": CoderAgent(),
            "tester": TesterAgent(),
            "reviewer": ReviewerAgent(),
        }
        self.allowed_tools = {name: agent.allowed_tools for name, agent in self.agents.items()}
        self.max_rounds = 10

    def step(self, goal: str, turn_order: List[str]) -> bool:
        """
        Выполняет один раунд действий всех агентов в заданном порядке.

        Параметры:
        -----------
        goal : str
            Текущая цель, которую система должна достичь.
        turn_order : List[str]
            Порядок обхода агентов в этом раунде.

        Логика работы:
        ---------------
        1. Для каждого агента в turn_order:
            - Получение сообщений из MessageBus (только для этого агента или broadcast).
            - Вызов метода agent.decide(goal, inbox) для выбора действия.
            - Логирование решения агента.

        2. Обработка действия агента:
            - AskAgent: пересылает сообщение указанному агенту.
            - UseTool: вызывает инструмент через Tools.call() при наличии прав, публикует результат в broadcast.
            - Reply: отправляет простое сообщение в broadcast.
            - Finish: публикует сообщение о завершении задачи и завершает оркестрацию.

        3. Если инструмент run_tests прошёл успешно, автоматически считается, что цель достигнута,
           и генерируется сообщение FINISH.

        Возвращает:
        -----------
        bool
            True, если задача достигнута и сгенерирован Finish, иначе False.
        """
        for name in turn_order:
            agent = self.agents[name]
            inbox = bus.receive_for(name)

            if inbox:
                Log.debug(f"[{name}] inbox ({len(inbox)}):")
                for m in inbox[-5:]:
                    Log.debug(f"  {m.sender}→{m.recipient}: {m.content[:200]}")

            try:
                decision = agent.decide(goal, inbox)
            except Exception as e:
                msg_text = f"Agent {name} failed to decide: {e}"
                Log.error(f"[orchestrator] {msg_text}")
                bus.send(BusMessage(sender="orchestrator", recipient=name, content=msg_text))
                continue

            Log.info(f"[{name}] decided: {decision.model_dump() if hasattr(decision,'model_dump') else decision}")

            step = decision.step

            # Обработка типа действия
            if isinstance(step, AskAgent):
                target = step.target
                bus.send(BusMessage(sender=name, recipient=target, content=step.message))
                Log.debug(f"[{name}] -> [ask->{target}]: {step.message[:200]}")

            elif isinstance(step, UseTool):
                tool = step.tool_name
                args = step.args or {}

                # Проверка прав на использование инструмента
                if tool not in self.allowed_tools.get(name, []):
                    msg = f"role {name} does not have access to tool {tool}. Allowed: {self.allowed_tools.get(name, [])}"
                    Log.warn(f"[orchestrator] DENIED: {msg}")
                    bus.send(BusMessage(sender="orchestrator", recipient=name, content=msg))
                    continue

                # Вызов инструмента
                try:
                    result = tools.call(tool, args)
                except Exception as e:
                    result = {"error": f"tool_exception: {e}\n{traceback.format_exc()}"}

                Log.info(f"[{name}] used {tool} -> {str(result)[:800]}")
                bus.send(BusMessage(sender=name, recipient="broadcast", content=f"tool {tool} result: {result}"))

                # Улучшенная коммуникация: отправка явных инструкций после определенных действий
                if name == "tester" and tool == "store_code" and args.get("filename") == "tests.py":
                    Log.info(f"[orchestrator] Обнаружено создание tests.py, инициирую запуск тестов")
                    # Отправляем прямую инструкцию тестировщику запустить тесты
                    next_instruction = (
                        "ВАЖНО: Ты успешно создал файл tests.py. "
                        "Теперь необходимо запустить тесты с помощью инструмента run_tests. "
                        "Используй следующие параметры: filename='solution.py', test_file='tests.py'"
                    )
                    bus.send(BusMessage(sender="orchestrator", recipient="tester", content=next_instruction))
                
                # Особая обработка: если run_tests прошёл успешно — завершение
                if tool == "run_tests" and isinstance(result, dict) and result.get("passed") is True:
                    summary = "Все тесты успешно пройдены. Задача выполнена!"
                    bus.send(BusMessage(sender="orchestrator", recipient="broadcast", 
                                      content=f"FINISH: {summary}"))
                    Log.info("[orchestrator] ✅ Тесты пройдены! Система завершает работу.")
                    return True
                
                # Если тесты не прошли, отправляем сообщение для исправления
                elif tool == "run_tests" and isinstance(result, dict) and result.get("passed") is False:
                    error_msg = result.get("error", "неизвестная ошибка")
                    Log.warn(f"[orchestrator] Тесты не прошли: {error_msg[:200]}")
                    
                    fix_instruction = (
                        f"ВНИМАНИЕ: Тесты не прошли с ошибкой: {error_msg[:200]}. "
                        f"Coder должен исправить код в solution.py, а затем Tester должен запустить тесты снова."
                    )
                    bus.send(BusMessage(sender="orchestrator", recipient="broadcast", content=fix_instruction))

            elif isinstance(step, Reply):
                bus.send(BusMessage(sender=name, recipient="broadcast", content=step.content))
                Log.debug(f"[{name}] reply -> broadcast: {step.content[:200]}")

            elif isinstance(step, Finish):
                bus.send(BusMessage(sender=name, recipient="broadcast", content=f"FINISH: {step.summary}"))
                Log.info(f"[{name}] finish -> broadcast: {step.summary[:200]}")
                return True

            else:
                msg = f"Unknown step type from agent {name}: {step}"
                Log.error("[orchestrator] " + msg)
                bus.send(BusMessage(sender="orchestrator", recipient=name, content=msg))

        return False

    def run(self, goal: str, order: Optional[List[str]] = None, max_rounds: int = 8):
        """
        Запускает цикл оркестрации до достижения цели или максимального количества раундов.

        Параметры:
        -----------
        goal : str
            Основная цель мультиагентной системы.
        order : Optional[List[str]]
            Порядок обхода агентов. По умолчанию: ["planner", "coder", "tester", "reviewer"].
        max_rounds : int
            Максимальное количество раундов (итераций взаимодействия агентов).

        Логика работы:
        ----------------
        1. Отправка стартового broadcast-сообщения от Planner.
        2. Итеративный вызов step() для каждого раунда.
        3. Если step() возвращает True, оркестрация считается завершённой.
        4. Если достигнут max_rounds — вывод сообщения о максимальном числе раундов.
        """
        if order is None:
            # Модифицируем порядок для первого раунда: вначале пусть работает планировщик и программист
            first_round_order = ["planner", "coder"]
            # В следующих раундах добавляем тестировщика и ревьюера
            next_rounds_order = ["tester", "reviewer", "planner", "coder"]
        else:
            first_round_order = order
            next_rounds_order = order

        Log.info("=== ORCHESTRATION START ===")
        bus.send(BusMessage(sender="planner", recipient="broadcast", content=f"start: {goal}"))

        # Первый раунд: создание решения
        Log.info(f"\n--- ROUND 1 (Разработка решения) ---")
        finished = self.step(goal, first_round_order)
        if finished:
            Log.info("=== ORCHESTRATION FINISHED ===")
            return
            
        # После создания решения, отправляем конкретную инструкцию тестировщику
        bus.send(BusMessage(
            sender="orchestrator", 
            recipient="tester", 
            content="Теперь твоя очередь. Выполни следующие шаги: 1) Прочитай solution.py через read_code, 2) Создай тесты в файле tests.py через store_code, 3) Запусти тесты через run_tests."
        ))

        # Последующие раунды
        for r in range(2, max_rounds + 1):
            Log.info(f"\n--- ROUND {r} (Тестирование и ревью) ---")
            finished = self.step(goal, next_rounds_order)
            if finished:
                Log.info("=== ORCHESTRATION FINISHED ===")
                return

        Log.warn("=== MAX ROUNDS REACHED ===")

