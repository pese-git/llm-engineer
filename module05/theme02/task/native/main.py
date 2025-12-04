import os
from agents import get_agents
from tools import get_tools
from llm import OpenAILLM
from dotenv import load_dotenv
from orchestrator import Orchestrator

load_dotenv()

def print_history(history):
    print("\n[Лог]")
    for step in history:
        sender = step.get('sender', '<NONE>')
        recipient = step.get('recipient', '<NONE>')
        action = step.get('meta', {}).get('action') or step.get('action', '')
        content = step.get('content', '')
        print(f"{sender} -> {recipient}: {action} {content}\n")

def main():
    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_API_BASE") or None
    llm = OpenAILLM(model="gpt-4o", api_key=api_key, base_url=base_url)
    agents = get_agents(llm=llm)
    tools = get_tools()
    task = "Реализовать функцию is_prime(n: int) -> bool, которая проверяет, является ли число простым."
    orchestrator = Orchestrator(agents=agents, tools=tools, task=task)
    context = orchestrator.run()

    from tools import ws as ws_tools
    print("\n[Файлы в рабочем пространстве]:")
    for fname, content in ws_tools.files.items():
        print(f"\n--- {fname} ---\n{content}")

    print_history(context["history"])

if __name__ == "__main__":
    main()
