from langgraph.graph import StateGraph, START, END
from agents import planner_node, coder_node, tester_node, reviewer_node
from tools import ws, get_tools

# GOAL
GOAL = "Реализовать функцию is_prime(n: int) -> bool, которая проверяет, является ли число простым."

def next_step(state):
    """Управляет направлением потока исполнения по ключу 'next'."""
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
builder.add_conditional_edges(
    "planner", next_step, ["coder", END]
)
builder.add_conditional_edges(
    "coder", next_step, ["tester", END]
)
builder.add_conditional_edges(
    "tester", next_step, ["reviewer", "coder", END]
)
builder.add_conditional_edges(
    "reviewer", next_step, ["coder", END]
)

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
