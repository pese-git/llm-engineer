from langgraph.graph import StateGraph, START, END
from agents import planner_node, coder_node, tester_node, reviewer_node
from tools import ws, get_tools
from dotenv import load_dotenv
import os

load_dotenv()

# GOAL
GOAL = "Реализовать функцию is_prime(n: int) -> bool, которая проверяет, является ли число простым."


def next_step(state):
    """Маршрутизация и лимит шагов."""
    if 'num_steps' in state:
        state['num_steps'] += 1
    else:
        state['num_steps'] = 1
    if state['num_steps'] >= 20:
        if 'log' in state:
            state['log'].append('[SYSTEM] Recursion limit reached. Pipeline завершён аварийно!')
        state['done'] = True
        return END
    if state.get('done', False) or not state.get('next'):
        return END
    return state['next']
# Сборка графа
builder = StateGraph(dict)
builder.add_node("planner", planner_node)
builder.add_node("coder", coder_node)
builder.add_node("tester", tester_node)
builder.add_node("reviewer", reviewer_node)

builder.add_edge(START, "planner")

# Весь flow идёт по ключу next_step(state)
all_agents = ["planner", "coder", "tester", "reviewer", END]
for agent in ["planner", "coder", "tester", "reviewer"]:
    builder.add_conditional_edges(agent, next_step, [a for a in all_agents if a != agent])

agent_graph = builder.compile()

def main():
    print(f"=== Multiagent LangGraph pipeline ===\nGOAL: {GOAL}\n")
    start_state = {
        "workspace": ws,
        "tools": get_tools(),
        "task": GOAL,
        "next": "planner",
        "done": False,
        "log": []
    }
    final = agent_graph.invoke(start_state)
    print("\n--- LOG ---")
    for entry in final.get("log", []):
        print(entry)
    print("\n--- Workspace files ---")
    for fname, content in ws.files.items():
        print(f"\n=== {fname} ===\n{content}")

if __name__ == "__main__":
    main()
