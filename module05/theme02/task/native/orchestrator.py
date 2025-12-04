from bus import Bus, BusMessage
from sgr import Finish, AskAgent

class Orchestrator:
    def __init__(self, agents, tools, task):
        self.tools = tools
        self.task = task
        self.bus = Bus()
        self.agent_map = {agent.name: agent for agent in agents}
        self.planner = self.agent_map['planner']

    def run(self):
        # Initial baton: manager → planner (начни работу, задача)
        self.bus.publish(BusMessage(
            sender="manager",
            recipient="planner",
            content=self.task,
            meta={"action": "ask_agent"}
        ))

        while not self.bus.is_empty():
            msg = self.bus._messages.popleft()
            print(f"\n[TRACE] Baton у {msg.recipient}: {msg.meta} :: content={msg.content}")
            print(f"[TRACE] Длина истории: {len(self.bus.get_history())}")
            context = {
                "task": self.task,
                "history": [h.dict() for h in self.bus.get_history()]
            }
            # 1. Если baton у planner — только Planner решает, что дальше
            if msg.recipient == "planner":
                print("[TRACE] Planner думает… (вызов LLM)")
                plan_step = self.planner.decide(context)
                # Если это finish — завершаем сценарий
                if hasattr(plan_step.step, "action") and plan_step.step.action == "finish":
                    finish_msg = BusMessage(
                        sender="planner",
                        recipient="manager",
                        content=getattr(plan_step.step, "summary", "Завершено!"),
                        meta={"action": "finish"},
                    )
                    self.bus.publish(finish_msg)
                    print("\n=== Process finished! (Planner дал finish) ===\n")
                    break
                assert isinstance(plan_step.step, AskAgent)
                ask = plan_step.step
                print(f"[TRACE] Planner выбрал: {ask.target}, message={ask.message}")
                baton_msg = BusMessage(
                    sender="planner",
                    recipient=ask.target,
                    content=ask.message,
                    meta={"action": "ask_agent"}
                )
                self.bus.publish(baton_msg)
                continue

            # 2. Если baton у coder/tester/reviewer — действие в их стиле
            agent = self.agent_map.get(msg.recipient)
            if not agent:
                print(f"[ОШИБКА] Не найден агент для {msg.recipient}")
                break
            print(f"[TRACE] Агент {msg.recipient}: выполняет decide…")
            context["history"] = [h.dict() for h in self.bus.get_history()]
            step = agent.decide(context).step

            # Если это use_tool — реально выполнить инструмент
            if hasattr(step, 'action') and step.action == 'use_tool':
                print(f"[TRACE] Агент {msg.recipient}: вызывает инструмент {step.tool_name}")
                tool_result = self.tools.call(step.tool_name, step.args)
                print(f"[TRACE] Результат инструмента: {tool_result}")
                tool_msg = BusMessage(
                    sender=msg.recipient,
                    recipient="planner",  # baton назад к planner
                    content=str(tool_result),
                    meta={"action": "use_tool", "tool": step.tool_name, "args": step.args}
                )
                self.bus.publish(tool_msg)
            elif hasattr(step, 'action') and step.action == 'finish':
                finish_msg = BusMessage(
                    sender=msg.recipient,
                    recipient="manager",
                    content=getattr(step, 'summary', 'Завершено'),
                    meta={"action": "finish"}
                )
                self.bus.publish(finish_msg)
                print("\n=== Process finished! ===\n")
                break
            else:
                print(f"[TRACE] Агент {msg.recipient}: возвращает reply/meta={getattr(step, 'action', 'reply')}")
                self.bus.publish(BusMessage(
                    sender=msg.recipient,
                    recipient="planner",
                    content=str(getattr(step, 'content', '')),
                    meta={"action": getattr(step, 'action', 'reply')}
                ))
        return {
            "history": [m.dict() for m in self.bus.get_history()]
        }
