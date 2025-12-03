import os
from agents import get_agents
from tools import get_tools
from llm import OpenAILLM
from dotenv import load_dotenv

load_dotenv()

def print_history(history):
    print("\n[Лог]")
    for step in history:
        print(f"{step['from']} -> {step['to']}: {step['action']} {step.get('tool','')} {step.get('params','')} {step.get('content','')}\n")

def main():
    # Считываем токен и base_url (если есть)
    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_API_BASE") or None
    llm = OpenAILLM(model="gpt-4o", api_key=api_key, base_url=base_url)
    
    agents = get_agents(llm=llm)
    tools = get_tools()
    agent_map = {agent.name: agent for agent in agents}

    context = {
        "task": "Реализовать функцию is_prime(n: int) -> bool, которая проверяет, является ли число простым.",
        "history": [],
    }
    current_agent = agent_map["planner"]

    import json
    while True:
        out = current_agent.decide(context)
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
        context["history"].append(step)
        print(f"\n[{step['from'].upper()} → {step['to'].upper()}] action={step['action']}, tool={step['tool']}")
        if step["content"]:
            print("Сообщение: ", step["content"])

        if step["action"] == "tool_call" and step["tool"]:
            tool_fn = tools[step["tool"]]
            tool_result = tool_fn(**step["params"])
            print(f"Tool '{step['tool']}' result:\n{tool_result}")

        if step["action"] == "done" or step["to"] == "manager":
            print("\n=== Процесс завершен! ===\n")
            break

        if step["to"] in agent_map:
            current_agent = agent_map[step["to"]]
        else:
            print(f"[ОШИБКА] Не найден агент: {step['to']}")
            break

    from tools import ws as ws_tools
    print("\n[Файлы в рабочем пространстве]:")
    for fname, content in ws_tools.files.items():
        print(f"\n--- {fname} ---\n{content}")

    print_history(context["history"])

if __name__ == "__main__":
    main()
