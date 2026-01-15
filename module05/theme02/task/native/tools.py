from typing import Dict, Any
from workspace import Workspace

class Tools:
    """
    Унифицированный набор инструментов для взаимодействия агентов
    с рабочим пространством в object-oriented стиле.
    """
    def __init__(self, ws: Workspace = None):
        self.ws = ws or Workspace()

    def call(self, tool_name: str, args: Dict[str, Any]) -> Any:
        args = args or {}
        if tool_name == "store_code":
            filename = args.get("filename", "solution.py")
            code = args.get("code") or args.get("content") or ""
            self.ws.store_code(filename, code)
            return {"status": "ok", "message": f"Код для {filename} сохранён."}

        if tool_name == "read_code":
            filename = args.get("filename", "solution.py")
            code = self.ws.read_code(filename)["code"]
            return {"status": "ok", "code": code}

        if tool_name == "run_python":
            from io import StringIO
            import sys, traceback
            import builtins
            buf = StringIO()
            old_stdout = sys.stdout
            sys.stdout = buf
            try:
                exec(
                    args.get("code", ""),
                    {"__builtins__": {
                        "print": print,
                        "range": range,
                        "len": len,
                        "int": int,
                        "float": float,
                        "str": str,
                        "bool": bool,
                        "list": list,
                        "dict": dict,
                        "set": set,
                        "type": type,
                        "object": object,
                        "globals": globals,
                        "isinstance": isinstance,
                        "issubclass": issubclass,
                        "__name__": "__main__",
                        "__import__": __import__,
                        "__build_class__": builtins.__build_class__,
                    }}
                )
                output = buf.getvalue()
                return {"status": "ok", "output": output}
            except Exception:
                err = "Ошибка:\n" + traceback.format_exc()
                return {"status": "error", "error": err}
            finally:
                sys.stdout = old_stdout

        if tool_name == "run_tests":
            filename = args.get("filename", "solution.py")
            test_file = args.get("test_file", "test_solution.py")
            code = self.ws.read_code(filename)["code"]
            tests = self.ws.read_code(test_file)["code"]
            if not code:
                return {"status": "error", "error": f"Нет файла {filename}"}
            if not tests:
                return {"status": "error", "error": f"Нет тестов в {test_file}"}
            # Удалить импорт решения из тестов (универсально)
            import re
            tests_clean = re.sub(r'^\s*from solution import .*$', '', tests, flags=re.MULTILINE)
            tests_clean = re.sub(r'^\s*import solution\s*$', '', tests_clean, flags=re.MULTILINE)
            # Удалить/заменить unittest.main()
            tests_clean = re.sub(
                r'^if __name__ == [\'"]__main__[\'"]:(.|\n)*?unittest\.main\(\)',
                '', tests_clean, flags=re.MULTILINE)
            # Добавить явный запуск вручную
            custom_test_runner = '''\nimport unittest\nimport sys\ndef _run_all_tests():\n    suite = unittest.TestSuite()\n    for obj in list(globals().values()):\n        if isinstance(obj, type) and issubclass(obj, unittest.TestCase):\n            suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(obj))\n    runner = unittest.TextTestRunner(stream=sys.stdout, verbosity=2)\n    result = runner.run(suite)\n_run_all_tests()\n'''
            full_code = code + "\n" + tests_clean + "\n" + custom_test_runner
            result = self.call("run_python", {"code": full_code})
            if result["status"] == "error":
                return {"status": "error", "error": result["error"]}
            return {"status": "ok", "message": "Все тесты пройдены!", "output": result["output"]}

        if tool_name == "lint_code":
            code = args.get("code", "")
            if not code:
                return {"status": "error", "error": "Не передан параметр code!"}
            if "    " in code and "\t" in code:
                return {"status": "error", "error": "Смешаны табы и пробелы!"}
            return {"status": "ok", "message": "Стиль кода в порядке."}

        if tool_name == "summarize_text":
            text = args.get("text", "")
            return {"status": "ok", "summary": text[:80] + ("..." if len(text) > 80 else "")}

        return {"status": "error", "error": f"Неизвестный инструмент '{tool_name}'"}

# Глобальный workspace и объект Tools — для совместимости main.py:
ws = Workspace()
tools_obj = Tools(ws)

def get_tools() -> Tools:
    return tools_obj