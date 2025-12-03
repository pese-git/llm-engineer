from agents import get_agents
from tools import get_tools
from workspace import Workspace

def print_history(history):
    print("\n[Лог]")
    for step in history:
        print(f"{step['from']} -> {step['to']}: {step['action']} {step.get('tool','')} {step.get('params','')} {step.get('content','')}")

def main():
    agents = get_agents()
    tools = get_tools()
    agent_map = {agent.name: agent for agent in agents}

    # Первое сообщение инициирует manager (его явно нет — цикл запустит planner)
    context = {
        "task": "Реализовать функцию is_prime(n: int) -> bool, которая проверяет, является ли число простым.",
        "history": [],
    }
    current_agent = agent_map["planner"]

    while True:
        # агент делает шаг
        out = current_agent.decide(context)
        step = {
            "from": current_agent.name,
            "to": out.get("recipient", ""),
            "action": out["action"],
            "tool": out.get("tool", ""),
            "params": out.get("params", {}),
            "content": out.get("content", ""),
        }
        context["history"].append(step)
        print(f"\n[{step['from'].upper()} → {step['to'].upper()}] action={step['action']}, tool={step['tool']}")
        if step["content"]:
            print("Сообщение: ", step["content"])

        # обработка: если tool_call — магический вызов инструмента
        if step["action"] == "tool_call" and step["tool"]:
            tool_fn = tools[step["tool"]]
            tool_result = tool_fn(**step["params"])
            print(f"Tool '{step['tool']}' result:\n{tool_result}")

        # завершение?
        if step["action"] == "done" or step["to"] == "manager":
            print("\n=== Процесс завершен! ===\n")
            break

        # следующий агент
        if step["to"] in agent_map:
            current_agent = agent_map[step["to"]]
        else:
            print(f"[ОШИБКА] Не найден агент: {step['to']}")
            break

    # Показать все файлы (артефакты)
    from tools import ws as ws_tools
    print("\n[Файлы в рабочем пространстве]:")
    for fname, content in ws_tools.files.items():
        print(f"\n--- {fname} ---\n{content}")

    print_history(context["history"])

if __name__ == "__main__":
    main()
