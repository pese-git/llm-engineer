from typing import Dict, Any
from workspace import Workspace

ws = Workspace()

def store_code(filename: str, code: str) -> str:
    ws.store_code(filename, code)
    return f"Код для {filename} сохранён."

def read_code(filename: str) -> str:
    return ws.read_code(filename)["code"]

def run_python(code: str) -> str:
    from io import StringIO
    import sys, traceback
    buf = StringIO()
    old_stdout = sys.stdout
    sys.stdout = buf
    result = ""
    try:
        exec(
            code,
            {"__builtins__": {"print": print, "range": range, "len": len, "int": int, "float": float, "str": str, "bool": bool}}
        )
        result = buf.getvalue()
    except Exception:
        result = "Ошибка:\n" + traceback.format_exc()
    finally:
        sys.stdout = old_stdout
    return result

def run_tests(filename: str = "solution.py", test_file: str = "test_solution.py") -> str:
    code = ws.read_code(filename)["code"]
    tests = ws.read_code(test_file)["code"]
    if not code:
        return f"Нет файла {filename}"
    if not tests:
        return f"Нет тестов в {test_file}"
    result = run_python(code + "\n" + tests)
    if result.startswith("Ошибка:"):
        return result
    return "Все тесты пройдены!\n" + result

def lint_code(code: str = None, **kwargs) -> str:
    if not code:
        return "Ошибка: от LLM не передан параметр code!"
    if "    " in code and "\t" in code:
        return "Смешаны табы и пробелы!"
    return "Стиль кода в порядке."

def summarize_text(text: str) -> str:
    return text[:80] + ("..." if len(text) > 80 else "")

def get_tools() -> Dict[str, Any]:
    return {
        "store_code": store_code,
        "read_code": read_code,
        "run_python": run_python,
        "run_tests": run_tests,
        "lint_code": lint_code,
        "summarize_text": summarize_text,
    }
