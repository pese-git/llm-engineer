from smolagents import CodeAgent, InferenceClientModel, OpenAIModel
from agents import get_agents
from dotenv import load_dotenv
import os

load_dotenv()
# Задайте модель HF или используйте дефолт.
# Можно явно передать token и model_id, например:
# model = InferenceClientModel(model_id="meta-llama/Llama-3.3-70B-Instruct", token="<YOUR_HF_TOKEN>")
#model = InferenceClientModel()  # Использует дефолтную модель HF
model = OpenAIModel(
    model_id="gpt-4o",
    api_key=os.environ["OPENAI_API_KEY"],
    api_base="https://api-openai.st.by/v1"  # для OpenRouter!
)

planner, coder, tester, reviewer = get_agents(model)

# Собираем менеджера, управляющего всеми ролями:
manager = CodeAgent(
    name="manager",
    description="Оркестратор команды агентов для сложных кодовых задач.",
    tools=[],
    managed_agents=[planner, coder, tester, reviewer],
    model=model
)

TASK = 'Реализовать функцию is_prime(n: int) -> bool, которая проверяет, является ли число простым.'

result = manager.run(TASK)

print("DONE\n---\n")
#print("Лог работы менеджера:")
#for log in manager.logs:
#    print(log)

from tools import ws
print(f"\nСодержимое файлов {ws.files}:")
for fname, content in ws.files.items():
    print(f"\n=== {fname} ===\n{content}")
