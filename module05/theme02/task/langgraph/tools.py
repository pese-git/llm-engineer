import sys
import traceback
from io import StringIO

class Workspace:
    """
    Simple in-memory file storage for agent collaboration.
    """
    def __init__(self):
        self.files = {}

ws = Workspace()

def store_code(filename, code):
    ws.files[filename] = code
    return {"message": f"stored {filename}", "filename": filename, "chars": len(code)}

def read_code(filename):
    return {"filename": filename, "code": ws.files.get(filename, "")}

def run_python(code):
    captured = StringIO()
    old = sys.stdout
    sys.stdout = captured
    out = {"stdout": "", "error": ""}
    import unittest  # разрешаем теперь внутри exec
    try:
        exec_globals = {
            "__builtins__": {
                "print": print,
                "range": range,
                "len": len,
                "int": int,
                "float": float,
                "str": str,
                "bool": bool,
            },
            "unittest": unittest,
            "__name__": "__main__"
        }
        exec(code, exec_globals)
        out["stdout"] = captured.getvalue()
    except Exception as e:
        out["error"] = traceback.format_exc()
    finally:
        sys.stdout = old
    return out

def run_tests(filename="solution.py", test_file="test_solution.py"):
    code = ws.files.get(filename, "")
    tests = ws.files.get(test_file, "")
    if not code:
        return {"passed": False, "error": f"Нет файла {filename}"}
    if not tests:
        return {"passed": False, "error": f"Нет тестов в {test_file}"}
    joined = code + "\n\n" + tests
    res = run_python(joined)
    if res["error"]:
        return {"passed": False, **res}
    return {"passed": True, **res}

def lint_code(code):
    issues = []
    if "    " in code and "\t" in code:
        issues.append("Смешение табуляций и пробелов")
    return {"issues": issues, "issue_count": len(issues)}

def summarize_text(text):
    return {"summary": text[:100] + ("..." if len(text) > 100 else "")}

def get_tools():
    return {
        "store_code": store_code,
        "read_code": read_code,
        "run_python": run_python,
        "run_tests": run_tests,
        "lint_code": lint_code,
        "summarize_text": summarize_text
    }

def get_workspace():
    return ws
