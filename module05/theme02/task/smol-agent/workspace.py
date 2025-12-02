import sys
import traceback
from io import StringIO

class Workspace:
    """
    In-memory файловая система и среда для кода — аналог вашей архитектуры.
    """
    def __init__(self):
        self.files = {}
    
    def store_code(self, filename, code):
        prev = self.files.get(filename, "")
        self.files[filename] = code
        return {
            "message": f"stored {filename}",
            "filename": filename,
            "chars": len(code),
            # diff опущен для простоты
        }

    def read_code(self, filename):
        return {"filename": filename, "code": self.files.get(filename, "")}

    def run_python(self, code):
        import unittest
        captured = StringIO()
        old = sys.stdout
        sys.stdout = captured
        out = {"stdout": "", "error": ""}
        try:
            allowed_builtins = {
                "print": print,
                "range": range,
                "len": len,
                "int": int,
                "float": float,
                "str": str,
                "bool": bool,
            }
            exec_globals = {
                "__builtins__": allowed_builtins,
                "unittest": unittest,
            }
            exec(code, exec_globals)
            out["stdout"] = captured.getvalue()
        except Exception as e:
            out["error"] = traceback.format_exc()
        finally:
            sys.stdout = old
        return out

    def run_tests(self, filename="solution.py", test_file="tests.py"):
        code = self.files.get(filename, "")
        tests = self.files.get(test_file, "")
        if not code:
            return {"passed": False, "error": f"Нет файла {filename}"}
        if not tests:
            return {"passed": False, "error": f"Нет тестов в {test_file}"}
        content = code + "\n\n" + tests
        res = self.run_python(content)
        res_out = {"passed": res["error"] == "", **res}
        return res_out
