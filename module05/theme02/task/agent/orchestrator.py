# ---------------------------
# Оркестратор — управление агентами, контроль инструментов, логирование
# ---------------------------
from typing import Any, Dict, List, Optional
from sgr import AskAgent, UseTool, Reply, Finish, BusMessage
from log import Log
from bus import MessageBus
from agent import PlannerAgent, CoderAgent, TesterAgent, ReviewerAgent
import traceback
from workspace import Workspace

# Переменная bus должна быть определена в main.py и передана сюда
# Этот импорт будет заполнен в runtime
bus = None
tools = None  # Аналогично для инструментов
ws = None  # Workspace будет также передан из main.py

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
        
    workflow_state : Dict
        Отслеживание состояния процесса для обеспечения правильной последовательности действий.
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
        # Отслеживание состояния рабочего процесса
        self.workflow_state = {
            "solution_created": False,
            "solution_read": False,
            "tests_created": False,
            "tests_run": False,
            "code_reviewed": False,
            "current_round": 0
        }

    def step(self, goal: str, turn_order: List[str]) -> bool:
        """
        Выполняет один раунд действий всех агентов в заданном порядке,
        с контролем состояния процесса и автоматической коррекцией отклонений.

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

        3. Проверка состояния процесса и отправка корректирующих указаний при необходимости.

        4. Если инструмент run_tests прошёл успешно, автоматически считается, что цель достигнута,
           и генерируется сообщение FINISH.

        Возвращает:
        -----------
        bool
            True, если задача достигнута и сгенерирован Finish, иначе False.
        """
        # Увеличиваем счетчик раундов
        self.workflow_state["current_round"] += 1
        Log.info(f"Раунд {self.workflow_state['current_round']}: состояние процесса = {self.workflow_state}")
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
                
                # Обновляем состояние рабочего процесса на основе выполненного инструмента
                if tool == "store_code":
                    filename = args.get("filename", "") or args.get("file", "")
                    code_content = args.get("code", "") or args.get("content", "")
                    if filename == "solution.py" and code_content:
                        self.workflow_state["solution_created"] = True
                        Log.info("[orchestrator] Отмечено создание solution.py")
                    elif filename == "tests.py" and code_content:
                        self.workflow_state["tests_created"] = True
                        Log.info("[orchestrator] Отмечено создание tests.py")
                
                elif tool == "read_code":
                    filename = args.get("filename", "")
                    if filename == "solution.py":
                        self.workflow_state["solution_read"] = True
                        Log.info("[orchestrator] Отмечено чтение solution.py")
                
                elif tool == "run_tests":
                    self.workflow_state["tests_run"] = True
                    Log.info("[orchestrator] Отмечен запуск тестов")
                    
                    # Проверяем результат выполнения тестов
                    if isinstance(result, dict) and result.get("passed") is True:
                        self.workflow_state["tests_passed"] = True
                        Log.info("[orchestrator] ✅ Тесты успешно пройдены")
                    else:
                        self.workflow_state["tests_passed"] = False
                        error_msg = result.get("error", "Неизвестная ошибка")
                        Log.warn(f"[orchestrator] Тесты не прошли: {error_msg[:200]}")
                
                elif tool == "lint_code":
                    self.workflow_state["code_reviewed"] = True
                    Log.info("[orchestrator] Отмечен обзор кода")
                
                # Особая обработка: если run_tests прошёл успешно — завершение
                if tool == "run_tests" and isinstance(result, dict) and result.get("passed") is True:
                    summary = "Все тесты успешно пройдены. Задача выполнена!"
                    bus.send(BusMessage(sender="orchestrator", recipient="broadcast", 
                                      content=f"FINISH: {summary}"))
                    Log.info("[orchestrator] ✅ Тесты пройдены! Система завершает работу.")
                    return True
                
                # Альтернативное условие завершения: если run_python запустил тесты успешно
                if tool == "run_python" and args.get("file", "").endswith("tests.py") and isinstance(result, dict) and not result.get("error"):
                    summary = "Тесты успешно пройдены через run_python. Задача выполнена!"
                    bus.send(BusMessage(sender="orchestrator", recipient="broadcast", 
                                      content=f"FINISH: {summary}"))
                    Log.info("[orchestrator] ✅ Тесты пройдены через run_python! Система завершает работу.")
                    return True
                
                # Если код протестирован с помощью run_python и в выводе нет ошибок
                if tool == "run_python" and "tests_code" in args and isinstance(result, dict) and not result.get("error"):
                    summary = "Код протестирован с помощью run_python и не содержит ошибок. Задача выполнена!"
                    bus.send(BusMessage(sender="orchestrator", recipient="broadcast", 
                                      content=f"FINISH: {summary}"))
                    Log.info("[orchestrator] ✅ Тесты, запущенные через run_python, прошли успешно! Система завершает работу.")
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
            
        # После обработки всех агентов проверяем состояние процесса и отправляем подсказки
        self._send_workflow_hints()
        
        # Проверяем, выполнены ли все необходимые шаги процесса
        if (self.workflow_state["solution_created"] and
            self.workflow_state["tests_created"] and 
            self.workflow_state["solution_read"] and
            self.workflow_state["tests_run"] and
            # Либо тесты успешно пройдены, либо мы уже в конце допустимых раундов
            (self.workflow_state["tests_passed"] or self.workflow_state["current_round"] >= self.max_rounds - 1) and
            self.workflow_state["code_reviewed"]):
            
            # Все необходимые этапы выполнены, завершаем процесс
            if self.workflow_state["tests_passed"]:
                summary = "Все этапы разработки выполнены успешно! Реализован is_prime, созданы тесты, которые успешно пройдены, проведен код ревью."
            else:
                summary = "Разработка завершена! Реализован is_prime, созданы тесты (есть ошибки запуска), проведен код ревью."
            bus.send(BusMessage(sender="orchestrator", recipient="broadcast", 
                              content=f"FINISH: {summary}"))
            Log.info("[orchestrator] 🎉 Все этапы разработки завершены! Система завершает работу.")
            return True
        
        return False
        
    def _send_workflow_hints(self):
        """
        Проверяет текущее состояние рабочего процесса и отправляет подсказки агентам
        для обеспечения правильной последовательности действий.
        """
        # Если solution.py создан, но tests.py еще нет, и тестировщик уже прочитал решение
        if (self.workflow_state["solution_created"] and 
            self.workflow_state["solution_read"] and 
            not self.workflow_state["tests_created"]):
            hint = (
                "СЛЕДУЮЩИЙ ШАГ: Тестировщику необходимо создать тесты.\n"
                "Используйте инструмент store_code с параметрами:\n"
                "filename='tests.py'\n"
                "code=[код с тестами для проверки функции]"
            )
            bus.send(BusMessage(sender="orchestrator", recipient="tester", content=hint))
            Log.info("[orchestrator] Отправлена подсказка тестировщику о создании тестов")
            
        # Если tests.py создан, но тесты еще не запущены
        elif (self.workflow_state["solution_created"] and
              self.workflow_state["tests_created"] and
              not self.workflow_state["tests_run"]):
            hint = (
                "СЛЕДУЮЩИЙ ШАГ: Необходимо запустить тесты.\n"
                "Используйте инструмент run_tests с параметрами:\n"
                "filename='solution.py'\n"
                "test_file='tests.py'"
            )
            bus.send(BusMessage(sender="orchestrator", recipient="tester", content=hint))
            Log.info("[orchestrator] Отправлена подсказка тестировщику о запуске тестов")
            
        # Если tests.py и solution.py были созданы, но solution.py пустой
        elif (self.workflow_state["solution_created"] and
              self.workflow_state["tests_created"] and
              "solution.py" in ws.files and
              not ws.files.get("solution.py", "")):
            warning = (
                "ВНИМАНИЕ: Файл solution.py существует, но не содержит кода.\n"
                "Coder: пожалуйста, реализуйте функцию в файле solution.py"
            )
            bus.send(BusMessage(sender="orchestrator", recipient="broadcast", content=warning))
            Log.warn("[orchestrator] Файл solution.py пуст, отправлено предупреждение")

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
        2. Адаптивная последовательность агентов в зависимости от состояния процесса.
        3. Итеративный вызов step() для каждого раунда.
        4. Если step() возвращает True, оркестрация считается завершённой.
        5. Если достигнут max_rounds — вывод сообщения о максимальном числе раундов.
        """
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
        2. Адаптивная последовательность агентов в зависимости от состояния процесса.
        3. Итеративный вызов step() для каждого раунда.
        4. Если step() возвращает True, оркестрация считается завершённой.
        5. Если достигнут max_rounds — вывод сообщения о максимальном числе раундов.
        """
        # Сбросим состояние рабочего процесса
        self.workflow_state = {
            "solution_created": False,
            "solution_read": False,
            "tests_created": False,
            "tests_run": False,
            "tests_passed": False,  # Новый флаг для отслеживания успешного прохождения тестов
            "code_reviewed": False,
            "current_round": 0
        }
        
        # Проверим наличие файлов в workspace и обновим состояние
        if "solution.py" in ws.files and ws.files.get("solution.py"):
            self.workflow_state["solution_created"] = True
            Log.info("[orchestrator] Обнаружен существующий solution.py")
            
        if "tests.py" in ws.files and ws.files.get("tests.py"):
            self.workflow_state["tests_created"] = True
            Log.info("[orchestrator] Обнаружен существующий tests.py")
        
        # Определение порядка агентов
        if order is None:
            # Стандартная последовательность
            all_agents_order = ["planner", "coder", "tester", "reviewer"]
        else:
            all_agents_order = order

        Log.info("=== ORCHESTRATION START ===")
        bus.send(BusMessage(sender="planner", recipient="broadcast", content=f"start: {goal}"))

        # Отправляем явную инструкцию каждому агенту
        agent_instructions = {
            "coder": "Реализуй функцию в solution.py, используя инструмент store_code.",
            "tester": "После чтения кода, создай тесты в tests.py, затем запусти тесты.",
            "reviewer": "Проверь качество кода с помощью lint_code и оцени его эффективность."
        }
        
        for agent_name, instruction in agent_instructions.items():
            bus.send(BusMessage(
                sender="orchestrator", 
                recipient=agent_name, 
                content=f"[ИНСТРУКЦИЯ]: {instruction}"
            ))

        # Адаптивная последовательность раундов
        current_round = 1
        while current_round <= max_rounds:
            Log.info(f"\n--- ROUND {current_round} ---")
            
            # Выбор оптимальной последовательности агентов в зависимости от состояния
            if not self.workflow_state["solution_created"]:
                round_order = ["planner", "coder"]
                Log.info("[orchestrator] Фокус на создание решения")
                
            elif self.workflow_state["solution_created"] and not self.workflow_state["tests_created"]:
                round_order = ["tester"]
                Log.info("[orchestrator] Фокус на создание тестов")
                
            elif self.workflow_state["tests_created"] and not self.workflow_state["tests_run"]:
                round_order = ["tester"]
                Log.info("[orchestrator] Фокус на запуск тестов")
                
            elif self.workflow_state["tests_run"] and not self.workflow_state["code_reviewed"]:
                round_order = ["reviewer"]
                Log.info("[orchestrator] Фокус на ревью кода")
                
            else:
                round_order = all_agents_order
            
            # Выполнение шага с выбранной последовательностью агентов
            finished = self.step(goal, round_order)
            if finished:
                Log.info("=== ORCHESTRATION FINISHED ===")
                return
            
            # Дополнительная проверка состояния после каждого раунда
            if current_round >= 4:  # Даем системе минимум 4 раунда для работы
                # Проверяем прогресс выполнения
                progress_score = 0
                max_progress = 6  # Увеличиваем максимальный балл, так как добавили новый флаг
                
                if self.workflow_state["solution_created"]: 
                    progress_score += 1
                if self.workflow_state["tests_created"]: 
                    progress_score += 1
                if self.workflow_state["solution_read"]: 
                    progress_score += 1
                if self.workflow_state["tests_run"]:
                    progress_score += 1
                if self.workflow_state["tests_passed"]:  # Добавляем учет успешности тестов
                    progress_score += 1
                if self.workflow_state["code_reviewed"]:
                    progress_score += 1
                
                # Если почти всё сделано (4 из 6 шагов) и мы близки к лимиту раундов
                if progress_score >= 4 and current_round >= max_rounds - 2:
                    tests_status = "успешно пройдены" if self.workflow_state['tests_passed'] else "запущены с ошибкой"
                    summary = f"Задача почти завершена! Выполнено {progress_score} из {max_progress} этапов: solution_created={self.workflow_state['solution_created']}, tests_created={self.workflow_state['tests_created']}, tests_run={self.workflow_state['tests_run']}, tests_passed={self.workflow_state['tests_passed']}, code_reviewed={self.workflow_state['code_reviewed']}. Тесты: {tests_status}"
                    Log.info(f"[orchestrator] 🏁 {summary}")
                    bus.send(BusMessage(sender="orchestrator", recipient="broadcast", 
                                     content=f"FINISH: {summary}"))
                    Log.info("=== ORCHESTRATION COMPLETED (Near Limit) ===")
                    return
            
            # Проверка на застревание - если состояние не меняется на протяжении нескольких раундов
            if current_round > 2 and self.workflow_state["current_round"] == current_round - 1:
                Log.warn("[orchestrator] Обнаружено застревание процесса. Отправляю корректирующие инструкции.")
                
                if not self.workflow_state["solution_created"]:
                    bus.send(BusMessage(
                        sender="orchestrator",
                        recipient="coder",
                        content="СРОЧНО: Необходимо создать файл solution.py с рабочей функцией!"
                    ))
                    
                elif not self.workflow_state["tests_created"]:
                    bus.send(BusMessage(
                        sender="orchestrator",
                        recipient="tester",
                        content="СРОЧНО: Необходимо создать файл tests.py с тестами!"
                    ))
                    
                elif not self.workflow_state["tests_run"]:
                    # Если solution.py и tests.py существуют, но тесты не запущены, 
                    # Orchestrator сам запускает тесты
                    if ("solution.py" in ws.files and ws.files.get("solution.py") and 
                        "tests.py" in ws.files and ws.files.get("tests.py")):
                        Log.info("[orchestrator] 🔄 Автоматический запуск тестов...")
                        try:
                            result = tools.call("run_tests", {
                                "filename": "solution.py",
                                "test_file": "tests.py"
                            })
                            if isinstance(result, dict) and result.get("passed", False):
                                self.workflow_state["tests_passed"] = True
                                summary = "Автоматически запущенные тесты успешно пройдены! Задача выполнена!"
                                bus.send(BusMessage(sender="orchestrator", recipient="broadcast", 
                                                  content=f"FINISH: {summary}"))
                                Log.info("[orchestrator] ✅ Тесты пройдены! Система завершает работу.")
                                return
                            else:
                                self.workflow_state["tests_passed"] = False
                                error_msg = result.get("error", "Неизвестная ошибка")
                                Log.warn(f"[orchestrator] ⚠️ Автоматические тесты не прошли: {error_msg[:200]}")
                                # Отправляем информацию о результатах тестирования
                                bus.send(BusMessage(
                                    sender="orchestrator",
                                    recipient="broadcast",
                                    content=f"АВТОМАТИЧЕСКОЕ ТЕСТИРОВАНИЕ: Тесты не прошли: {error_msg[:200]}"
                                ))
                        except Exception as e:
                            Log.error(f"[orchestrator] Ошибка при автоматическом запуске тестов: {e}")
                    else:
                        bus.send(BusMessage(
                            sender="orchestrator",
                            recipient="tester",
                            content="СРОЧНО: Необходимо запустить тесты с помощью инструмента run_tests!"
                        ))
            
            current_round += 1

        # Печатаем итоговый статус системы
        Log.warn("=== MAX ROUNDS REACHED ===")
        Log.info(f"Итоговое состояние: {self.workflow_state}")

