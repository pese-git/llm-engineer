from bus import Bus

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

    def run(self):
        import json
        # Первое сообщение от менеджера (или от planner, если без менеджера)
        initial_step = {
            "from": "manager",
            "to": "planner",
            "action": "message",
            "tool": None,
            "params": {},
            "content": self.task,
        }
        self.bus.publish(initial_step)
        
        while not self.bus.is_empty():
            next_agent_name = None
            for msg in self.bus._messages:
                if msg.get("to") in self.agent_map:
                    next_agent_name = msg["to"]
                    break
            if not next_agent_name:
                print("[ОШИБКА] Нет агента для обработки сообщения; завершение.")
                break
            msg = self.bus.get_next_for(next_agent_name)
            if not msg:
                break
            current_agent = self.agent_map[next_agent_name]
            self.context["history"] = self.bus.get_history()
            agent_out = current_agent.decide(self.context)
            if isinstance(agent_out, str):
                try:
                    agent_out = json.loads(agent_out)
                except Exception:
                    raise RuntimeError(f"Agent returned a string that is not JSON: {agent_out}")
            step = {
                "from": current_agent.name,
                "to": agent_out.get("recipient", ""),
                "action": agent_out.get("action", ""),
                "tool": agent_out.get("tool", ""),
                "params": agent_out.get("params", {}),
                "content": agent_out.get("content", ""),
            }
            from_name = str(step.get('from') or '<NONE>').upper()
            to_name = str(step.get('to') or '<NONE>').upper()
            print(f"\n[{from_name} → {to_name}] action={step['action']}, tool={step['tool']}")
            if step["content"]:
                print("Сообщение: ", step["content"])
            if step["action"] == "tool_call" and step["tool"]:
                tool_fn = self.tools[step["tool"]]
                tool_result = tool_fn(**step["params"])
                print(f"Tool '{step['tool']}' result:\n{tool_result}")
            self.bus.publish(step)
            if step["action"] == "done" or step["to"] == "manager":
                print("\n=== Процесс завершен! ===\n")
                break
            if len(self.bus.get_history()) > 50:
                print("[ОШИБКА] Слишком длинная история; emergency stop.")
                break
        self.context["history"] = self.bus.get_history()
        return self.context
