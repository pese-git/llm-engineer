# LangGraph agent nodes: все обычные функции (без декоратора @node)
import json
import ast
from langchain_core.messages import SystemMessage, HumanMessage
from llm import get_llm

def log_and_print(msg, log):
    print(msg)
    log.append(msg)

def robust_json_parse(text):
    try:
        return json.loads(text)
    except Exception:
        try:
            return ast.literal_eval(text)
        except Exception:
            return None

def planner_node(state):
    ws, tools = state['workspace'], state['tools']
    log = state.get('log') or []
    llm = get_llm()
    prompt = (
        "Ты — AI-планировщик. Если задача полностью решена (код реализован, тесты проходят, замечаний нет) или все review положительные — ОБЯЗАТЕЛЬНО верни {'action': 'finish'}!\n"
        "ВАЖНО: Ответ ТОЛЬКО в формальном JSON, c двойными кавычками, без пояснений!"
        f"\nТЕКУЩИЕ ФАЙЛЫ: {json.dumps(ws.files)}\n"
        f"ЗАДАЧА: {state['task']}\n"
        f"Последние сообщения: {log[-2:]}\n"
        "Ответь СТРОГО в формате JSON: {'action': 'assign', 'recipient': 'coder'|'tester'|'reviewer', 'instruction': ...} или {'action': 'finish'}"
    )
    log_and_print(f"[PLANNER/DEBUG] PROMPT:\n{prompt}", log)
    response = llm.invoke([
        SystemMessage(content=prompt)
    ])
    log_and_print(f"[PLANNER/DEBUG] RAW LLM RESPONSE: {getattr(response, 'content', str(response))}", log)
    result = robust_json_parse(getattr(response, "content", "{}"))
    if not result:
        result = {"action": "assign", "recipient": "coder", "instruction": "Стандартное делегирование"}
        log_and_print(f"[PLANNER/LLM/ERROR] Не удалось распарсить JSON: {response}", log)
    if result.get('action') == 'assign' and result.get('recipient') in ("coder", "tester", "reviewer"):
        state['next'] = result['recipient']
        log_and_print(f"[PLANNER/LLM] Делегирую {result['recipient']}: {result.get('instruction')}", log)
        state['done'] = False
    elif result.get('action') == 'finish':
        log_and_print(f"[PLANNER/LLM] Pipeline завершён по решению планировщика!", log)
        state['done'] = True
        state.pop('next', None)
    else:
        log_and_print(f"[PLANNER/LLM] Некорректный ответ, по умолчанию → coder", log)
        state['next'] = 'coder'
        state['done'] = False
    state['log'] = log
    return state

def coder_node(state):
    ws, tools = state['workspace'], state['tools']
    log = state.get('log') or []
    llm = get_llm()
    prompt = (
        "Ты — AI-программист. Всегда используй инструменты только через store_code('solution.py', ...)!\nВАЖНО: Ответ ТОЛЬКО в valid JSON-формате, только двойные кавычки, без пояснений!\n"
        f"ТЕКУЩИЕ ФАЙЛЫ: {json.dumps(ws.files)}\n"
        f"ЗАДАЧА: {state['task']}\n"
        f"Последние замечания: {log[-1] if log else ''}\n"
        "Ответь СТРОГО в формате JSON: {'action': store_code, 'code': ...} или {'action': 'skip'}"
    )
    log_and_print(f"[CODER/DEBUG] PROMPT:\n{prompt}", log)
    response = llm.invoke([
        SystemMessage(content=prompt)
    ])
    log_and_print(f"[CODER/DEBUG] RAW LLM RESPONSE: {getattr(response, 'content', str(response))}", log)
    result = robust_json_parse(getattr(response, "content", "{}"))
    if not result:
        result = {"action": "skip"}
        log_and_print(f"[CODER/LLM/ERROR] Не удалось распарсить JSON от LLM: {response}", log)
    if result.get('action') == 'store_code' and 'code' in result:
        tools['store_code']('solution.py', result['code'])
        log_and_print(f"[CODER/LLM] Сохранил через инструмент: {len(result['code'])} символов", log)
        state['next'] = 'tester'
        state['done'] = False
    else:
        log_and_print(f"[CODER/LLM] Ошибка или пропуск: {result}", log)
        state['next'] = 'planner'
        state['done'] = False
    state['log'] = log
    return state

def tester_node(state):
    ws, tools = state['workspace'], state['tools']
    log = state.get('log') or []
    llm = get_llm()
    prompt = (
        "Ты — AI-тестировщик. Все тестовые действия только через инструменты. ВАЖНО: Ответ обязательно ТОЛЬКО в valid JSON, с двойными кавычками!\n"
        f"ТЕКУЩИЕ ФАЙЛЫ: {json.dumps(ws.files)}\n"
        f"ЗАДАЧА: {state['task']}\n"
        f"Последние замечания: {log[-1] if log else ''}\n"
        "Ответь СТРОГО в формате JSON: {'action': store_code, 'test_code': ...} или {'action': run_tests, 'filename': ..., 'test_file': ...} или {'action': 'skip'}"
    )
    log_and_print(f"[TESTER/DEBUG] PROMPT:\n{prompt}", log)
    response = llm.invoke([
        SystemMessage(content=prompt)
    ])
    log_and_print(f"[TESTER/DEBUG] RAW LLM RESPONSE: {getattr(response, 'content', str(response))}", log)
    result = robust_json_parse(getattr(response, "content", "{}"))
    if not result:
        result = {"action": "skip"}
        log_and_print(f"[TESTER/LLM/ERROR] Не удалось распарсить JSON: {response}", log)
    if result.get('action') == 'store_code' and 'test_code' in result:
        tools['store_code']('test_solution.py', result['test_code'])
        log_and_print(f"[TESTER/LLM] Сохранил тесты, далее вызовет run_tests", log)
        res = tools['run_tests']('solution.py', 'test_solution.py')
        log_and_print(f"[TESTER/LLM] Запуск тестов: {'OK' if res['passed'] else 'FAIL'}\n{res}", log)
        state['next'] = 'reviewer' if res['passed'] else 'coder'
        state['done'] = False
    elif result.get('action') == 'run_tests':
        filename = result.get('filename', 'solution.py')
        testfile = result.get('test_file', 'test_solution.py')
        res = tools['run_tests'](filename, testfile)
        log_and_print(f"[TESTER/LLM] Запуск тестов: {'OK' if res['passed'] else 'FAIL'}\n{res}", log)
        state['next'] = 'reviewer' if res['passed'] else 'coder'
        state['done'] = False
    else:
        log_and_print(f"[TESTER/LLM] Ошибка или пропуск: {result}", log)
        state['next'] = 'coder'
        state['done'] = False
    state['log'] = log
    return state

def reviewer_node(state):
    ws, tools = state['workspace'], state['tools']
    log = state.get('log') or []
    llm = get_llm()
    prompt = (
        "Ты — AI-код-ревьюер. Если код полностью корректен и замечаний нет — обязательно возвращай {'action': 'finish'} для завершения пайплайна! Иначе возвращай {'action': 'lint_code'} с комментариями.\n"
        f"ТЕКУЩИЕ ФАЙЛЫ: {json.dumps(ws.files)}\n"
        f"ЗАДАЧА: {state['task']}\n"
        f"Последние замечания: {log[-1] if log else ''}\n"
        "Ответь СТРОГО в формате JSON: {'action': 'finish'} или {'action': 'lint_code'} или {'action': 'skip'}"
    )
    log_and_print(f"[REVIEWER/DEBUG] PROMPT:\n{prompt}", log)
    response = llm.invoke([
        SystemMessage(content=prompt)
    ])
    log_and_print(f"[REVIEWER/DEBUG] RAW LLM RESPONSE: {getattr(response, 'content', str(response))}", log)
    try:
        result = json.loads(getattr(response, "content", "{}"))
    except Exception:
        result = {"action":"skip"}
        log_and_print(f"[REVIEWER/LLM/ERROR] Не удалось распарсить JSON: {response}", log)
    if result.get('action') == 'finish':
        log_and_print(f"[REVIEWER/LLM] Pipeline завершён LLM!", log)
        state['done'] = True
        state.pop('next', None)
    elif result.get('action') == 'lint_code':
        code = ws.files.get('solution.py', "")
        issues = tools['lint_code'](code)
        if issues['issue_count'] == 0:
            log_and_print(f"[REVIEWER/LLM] Нет замечаний, pipeline завершён!", log)
            state['done'] = True
            state.pop('next', None)
        else:
            log_and_print(f"[REVIEWER/LLM] Стиль не ОК: {issues['issues']} — возврат кодеру", log)
            state['next'] = 'coder'
            state['done'] = False
    else:
        log_and_print(f"[REVIEWER/LLM] Нет решения, передача planner", log)
        state['next'] = 'planner'
        state['done'] = False
    state['log'] = log
    return state
