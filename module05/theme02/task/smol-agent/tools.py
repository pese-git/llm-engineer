from smolagents import tool
from workspace import Workspace

ws = Workspace()

@tool
def store_code(filename: str, code: str) -> str:
    """
    Сохраняет код в память под именем файла.
    Args:
        filename: Имя файла для сохранения.
        code: Код, который нужно сохранить.
    """
    print(f"[TOOL CALL] store_code(filename={filename}, code=[{len(code)} chars])")
    ws.files[filename] = code
    return f"Код для {filename} сохранён ({len(code)} символов)"

@tool
def read_code(filename: str) -> str:
    """
    Читает содержимое файла.
    Args:
        filename: Имя файла для чтения.
    """
    return ws.files.get(filename, "")

@tool
def run_python(code: str) -> str:
    """
    Выполняет переданный Python-код и возвращает результат или описание ошибки.
    Args:
        code: Код, который нужно выполнить.
    """
    import sys, traceback
    from io import StringIO
    buf = StringIO(); old = sys.stdout; sys.stdout = buf
    try:
        exec(code, {"__builtins__": {"print": print, "range": range, "len": len, "int": int, "float": float, "str": str, "bool": bool}})
    except Exception:
        result = traceback.format_exc()
    else:
        result = buf.getvalue()
    finally:
        sys.stdout = old
    return result

@tool
def run_tests(filename: str = "solution.py", test_file: str = "tests.py") -> str:
    """
    Запускает тесты из test_file к решению в filename.
    Args:
        filename: Имя файла с решением.
        test_file: Имя файла с тестами.
    """
    code = ws.files.get(filename, "")
    tests = ws.files.get(test_file, "")
    if not code:
        return f"Нет файла {filename}"
    if not tests:
        return f"Нет тестов в {test_file}"
    return run_python(code + "\n" + tests)

@tool
def lint_code(code: str) -> str:
    """
    Проверяет стиль кода на наличие смешения табов и пробелов.
    Args:
        code: Исходный код для проверки.
    """
    if "    " in code and "\t" in code:
        return "Проблема: смешаны табы и пробелы!"
    return "Стиль кода в порядке."

@tool
def summarize_text(text: str) -> str:
    """
    Делает краткую сводку текста.
    Args:
        text: Текст для суммаризации.
    """
    return text[:80] + ("..." if len(text) > 80 else "")

def get_tools():
    return {
        "store_code": store_code,
        "read_code": read_code,
        "run_python": run_python,
        "run_tests": run_tests,
        "lint_code": lint_code,
        "summarize_text": summarize_text
    }
