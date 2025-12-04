class Orchestrator:
    def __init__(self, agents, tools, task):
        """
        agents: List of agent objects (each should have .name and .decide())
        tools: dict name -> callable
        task: str (task description)
        """
        self.agents = agents
        self.tools = tools
        self.task = task
        self.agent_map = {agent.name: agent for agent in agents}
        self.context = {
            "task": task,
            "history": [],
        }

    def run(self):
        """Runs the agent orchestration loop."""
        current_agent = self.agent_map.get("planner")
        import json

        while True:
            out = current_agent.decide(self.context)
            if isinstance(out, str):
                try:
                    out = json.loads(out)
                except Exception:
                    raise RuntimeError(f"Agent returned a string that is not JSON: {out}")
            step = {
                "from": current_agent.name,
                "to": out.get("recipient", ""),
                "action": out.get("action", ""),
                "tool": out.get("tool", ""),
                "params": out.get("params", {}),
                "content": out.get("content", ""),
            }
            self.context["history"].append(step)
            from_ = str(step['from']).upper() if step['from'] else "<NONE>"
            to_ = str(step['to']).upper() if step['to'] else "<NONE>"
            print(f"\n[{from_} → {to_}] action={step['action']}, tool={step['tool']}")
            if step["content"]:
                print("Сообщение: ", step["content"])

            if step["action"] == "tool_call" and step["tool"]:
                tool_fn = self.tools[step["tool"]]
                tool_result = tool_fn(**step["params"])
                print(f"Tool '{step['tool']}' result:\n{tool_result}")

            if step["action"] == "done" or step["to"] == "manager":
                print("\n=== Процесс завершен! ===\n")
                break

            if step["to"] in self.agent_map:
                current_agent = self.agent_map[step["to"]]
            else:
                print(f"[ОШИБКА] Не найден агент: {step['to']}")
                break
        return self.context
