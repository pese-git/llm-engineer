# LangGraph agent nodes: все обычные функции (без декоратора @node)
def planner_node(state):
    log = state.get('log') or []
    log.append('[PLANNER] ➔ Постановка задачи — передаю работу кодеру')
    state['log'] = log
    state['next'] = 'coder'
    state['done'] = False
    return state

def coder_node(state):
    ws, tools = state['workspace'], state['tools']
    log = state.get('log') or []
    code = (
        "def is_prime(n: int) -> bool:\n"
        "    if n <= 1:\n        return False\n"
        "    if n <= 3:\n        return True\n"
        "    if n % 2 == 0 or n % 3 == 0:\n        return False\n"
        "    i = 5\n    while i * i <= n:\n        if n % i == 0 or n % (i + 2) == 0:\n            return False\n        i += 6\n    return True"
    )
    tools['store_code']('solution.py', code)
    log.append(f"[CODER] ➔ Сохранил функцию в solution.py\n{code}")
    state['log'] = log
    state['next'] = 'tester'
    state['done'] = False
    return state

def tester_node(state):
    ws, tools = state['workspace'], state['tools']
    log = state.get('log') or []
    test_code = (
        "import unittest\nfrom solution import is_prime\n\n"
        "class TestIsPrime(unittest.TestCase):\n"
        "    def test_main(self):\n        self.assertTrue(is_prime(13))\n        self.assertFalse(is_prime(1))\n        self.assertTrue(is_prime(2))\n        self.assertFalse(is_prime(6))\n\nif __name__=='__main__':\n    unittest.main()"
    )
    tools['store_code']('test_solution.py', test_code)
    result = tools['run_tests']('solution.py', 'test_solution.py')
    log.append(f"[TESTER] ➔ Сохранил тест и запустил: {'OK' if result['passed'] else 'FAIL'}\n{result}")
    if result.get("passed"):
        state['log'] = log
        state['next'] = 'reviewer'
        state['done'] = False
        return state
    else:
        state['log'] = log
        state['next'] = 'coder'
        state['done'] = False
        return state

def reviewer_node(state):
    ws, tools = state['workspace'], state['tools']
    log = state.get('log') or []
    code = ws.files.get('solution.py', "")
    issues = tools['lint_code'](code)
    if issues['issue_count'] == 0:
        log.append(f"[REVIEWER] ➔ Нет замечаний, pipeline завершён!")
        state['done'] = True
        state.pop('next', None)  # удаляем next полностью!
    else:
        log.append(f"[REVIEWER] ➔ Стиль не ОК: {issues['issues']} — возврат кодеру")
        state['next'] = 'coder'
    state['log'] = log
    return state
