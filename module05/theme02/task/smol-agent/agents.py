from smolagents import ToolCallingAgent, InferenceClientModel
from tools import get_tools

def get_agents(model):
    tools = get_tools()
    planner = ToolCallingAgent(
        name="planner",
        description="Планирует процесс: разбивает цель на этапы и распределяет задачи. Всегда инструктируй coder использовать store_code с filename='solution.py' для сохранения решений и tester — для тестов! Пример: store_code('solution.py', 'def ...'). Все задания должны быть оформлены КАК ВЫЗОВЫ инструментов, а не просто print или финальные ответы! Запрещено завершать задачу или вызывать final_answer, пока не будет вызван store_code для всех решений!",
        tools=[],
        model=model,
    )
    coder = ToolCallingAgent(
        name="coder",
        description="Реализует Python-функции и СТРОГО сохраняет их в solution.py исключительно через инструмент store_code. Всегда вызывай store_code('solution.py', ...)! Любые другие имена файлов запрещены для основного решения. ЕДИНСТВЕННЫЙ СПОСОБ дать решение — это вызвать store_code('solution.py', ...). Запрещено отвечать final_answer / завершать работу, пока не сделано сохранение через store_code. Для линтинга — lint_code, для запуска — run_python.",
        tools=[tools['store_code'], tools['read_code'], tools['run_python'], tools['lint_code']],
        model=model,
    )
    tester = ToolCallingAgent(
        name="tester",
        description="Создает, сохраняет и запускает тесты для решения, анализирует их результат. Всегда сохраняй тесты только через store_code('test_solution.py', ...), запуск тестов — через run_tests(filename='solution.py', test_file='test_solution.py'). Используй ТОЛЬКО инструменты store_code (для тестов), read_code и run_tests с фиксированными именами файлов. Запрещено использовать любые другие имена файлов для решений/тестов! Запрещено выдавать результат final_answer, пока не были вызваны store_code и run_tests!",
        tools=[tools['store_code'], tools['read_code'], tools['run_tests']],
        model=model,
    )
    reviewer = ToolCallingAgent(
        name="reviewer",
        description="Проверяет стиль, качество и эффективность кода, использует только read_code, lint_code, summarize_text. Выдача результата происходит только через инструменты.",
        tools=[tools['read_code'], tools['lint_code'], tools['summarize_text']],
        model=model,
    )
    return planner, coder, tester, reviewer
