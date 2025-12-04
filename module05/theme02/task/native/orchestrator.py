from bus import Bus
from sgr import AgentStep, AskAgent, UseTool, Finish, BusMessage

class Orchestrator:
    def __init__(self, agents, tools, task):
        self.agents = agents
        self.tools = tools
        self.task = task
        self.agent_map = {agent.name: agent for agent in agents}
        self.bus = Bus()
        self.context = {
            "task": task,
            "history": [],
        }
        # Кому передавать baton после atomic-step
        self.baton_map = {
            "planner": "coder",
            "coder": "tester",
            "tester": "reviewer",
            "reviewer": "manager",
        }
        # Для ретраев и эскалации (фиксируется на уровне всего процесса)
        self.MAX_RETRIES = 3
        self.retry_count = 0
        self.last_test_fail = None

    def run(self):
        # Первое сообщение для старта пайплайна — Planner даёт задание Coder
        initial_message = BusMessage(
            sender="manager",
            recipient="planner",
            content=self.task,
            meta={"action": "ask_agent"},
        )
        self.bus.publish(initial_message)
        
        import json
        baton_recipient = None
        while not self.bus.is_empty():
            next_agent_name = None
            for msg in self.bus._messages:
                if msg.recipient in self.agent_map:
                    next_agent_name = msg.recipient
                    break
            if not next_agent_name:
                print("[ОШИБКА] Нет агента для обработки сообщения; завершение.")
                break
            msg = self.bus.get_next_for(next_agent_name)
            if not msg:
                break
            current_agent = self.agent_map[next_agent_name]
            self.context["history"] = [m.dict() for m in self.bus.get_history()]
            agent_step = current_agent.decide(self.context)
            actual_step = agent_step.step
            from_name = str(current_agent.name or '<NONE>').upper()
            action_type = actual_step.action
            # baton-получатель для передачи bus-сообщения
            baton_recipient = self.baton_map.get(current_agent.name)

            print(f"\n[{from_name}] action={action_type}")
            if hasattr(actual_step, 'message'):
                print("Сообщение:", actual_step.message)
            elif hasattr(actual_step, 'content'):
                print("Сообщение:", actual_step.content)
            elif hasattr(actual_step, 'summary'):
                print("Завершение:", actual_step.summary)

            # (1) ask_agent — только у Planner, baton auto (recipient = baton_map)
            if action_type == "ask_agent":
                # Planner задаёт task, отдаём baton coder
                meta = {"action": action_type}
                bus_message = BusMessage(
                    sender=current_agent.name,
                    recipient=baton_recipient or "coder",
                    content=actual_step.message,
                    meta=meta,
                )
                self.bus.publish(bus_message)
            # (2) use_tool — Orchestrator после успешного вызова baton-ит next agent
            elif action_type == "use_tool":
                tool_result = self.tools.call(actual_step.tool_name, actual_step.args)
                print(f"Tool '{actual_step.tool_name}' result:\n{tool_result}")
                meta = {"action": action_type, "tool": actual_step.tool_name, "args": actual_step.args}
                bus_message = BusMessage(
                    sender=current_agent.name,
                    recipient=current_agent.name, # такой step останется для истории
                    content=str(tool_result) if tool_result is not None else '',
                    meta=meta,
                )
                self.bus.publish(bus_message)
                # Автоматический запуск run_tests после store_code тестов
                if (
                    current_agent.name == "tester"
                    and actual_step.tool_name == "store_code"
                    and actual_step.args.get("filename") == "test_solution.py"
                ):
                    print("[AUTO] Автозапуск run_tests от tester после создания test_solution.py")
                    tool_result_run = self.tools.call(
                        "run_tests", {"filename": "solution.py", "test_file": "test_solution.py"}
                    )
                    meta_run = {"action": "use_tool", "tool": "run_tests", "args": {"filename": "solution.py", "test_file": "test_solution.py"}}
                    bus_message_run = BusMessage(
                        sender=current_agent.name,
                        recipient=current_agent.name,
                        content=str(tool_result_run),
                        meta=meta_run,
                    )
                    self.bus.publish(bus_message_run)
                # Обработка неудачных тестов (эскалация и ретрай)
                if actual_step.tool_name == "run_tests":
                    # критерием успешности считаем статус результата
                    if not (isinstance(tool_result, dict) and tool_result.get("status") == "ok"):
                        self.retry_count += 1
                        self.last_test_fail = tool_result
                        if self.retry_count <= self.MAX_RETRIES:
                            print(f"[RETRY] Тесты не пройдены! Возврат кодеру. Попытка {self.retry_count}/{self.MAX_RETRIES}")
                            retry_message = BusMessage(
                                sender="tester",
                                recipient="coder",
                                content=f"Тесты не пройдены (попытка {self.retry_count}/{self.MAX_RETRIES}):\n{tool_result}",
                                meta={"action": "ask_agent", "retry": self.retry_count}
                            )
                            self.bus.publish(retry_message)
                            continue  # не baton'им дальше, а возвращаем codеру задачу
                        else:
                            print(f"[FAIL] Тесты так и не пройдены за {self.MAX_RETRIES} попыток. Останавливаемся.")
                            fail_finish = Finish(action="finish", summary=f"Не удалось пройти тесты за {self.MAX_RETRIES} попыток. Последняя ошибка: {tool_result}")
                            fail_message = BusMessage(
                                sender="tester",
                                recipient="manager",
                                content=fail_finish.summary,
                                meta={"action": "finish", "fail": True}
                            )
                            self.bus.publish(fail_message)
                            print("\n=== Процесс завершен с ошибкой! ===\n")
                            break
                    else:
                        self.retry_count = 0
                        self.last_test_fail = None
                # Baton (если не последний агент)
                if baton_recipient and baton_recipient != "manager":
                    baton_message = BusMessage(
                        sender=current_agent.name,
                        recipient=baton_recipient,
                        content=f"Передай baton агенту {baton_recipient}",
                        meta={"action": "ask_agent", "autogen": True}
                    )
                    self.bus.publish(baton_message)
                elif baton_recipient == "manager":
                    # Завершающее действие — выдать finish
                    finish = Finish(action="finish", summary=f"{current_agent.name} завершил финальный шаг.")
                    finish_message = BusMessage(
                        sender=current_agent.name,
                        recipient="manager",
                        content=finish.summary,
                        meta={"action": "finish"}
                    )
                    self.bus.publish(finish_message)
                    print("\n=== Процесс завершен! ===\n")
                    break
            elif action_type == "finish":
                finish_message = BusMessage(
                    sender=current_agent.name,
                    recipient="manager",
                    content=actual_step.summary,
                    meta={"action": action_type},
                )
                self.bus.publish(finish_message)
                print("\n=== Процесс завершен! ===\n")
                break
            if len(self.bus.get_history()) > 50:
                print("[ОШИБКА] Слишком длинная история; emergency stop.")
                break
        self.context["history"] = [m.dict() for m in self.bus.get_history()]
        return self.context
