from typing import Any, Dict, List, Optional
from log import Log
from workspace import Workspace

class Tools:
    """
    Набор инструментов, доступных агентам системы оркестрации.

    Этот класс является адаптером между агентами (planner, coder, tester и др.)
    и внутренней виртуальной рабочей средой Workspace, предоставляя единый
    интерфейс для выполнения действий над кодом и файлами.

    Каждый инструмент вызывается через метод `call()`, который маршрутизирует
    запрос к соответствующему методу Workspace или выполняет встроенную
    функциональность (например, lint).

    Поддерживаемые инструменты и их логирование описаны внутри call().
    """

    def __init__(self, ws: Workspace):
        """
        Инициализация набора инструментов.

        Параметры:
        ----------
        ws : Workspace
            Объект виртуальной рабочей среды, предоставляющий низкоуровневые
            операции над файлами и исполняемым кодом.
        """
        self.ws = ws

    def call(self, tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """
        Основной интерфейс вызова инструментов.

        На основе имени инструмента вызывает соответствующие методы Workspace
        либо выполняет встроенную логику. Логирует вызовы и результаты.

        Параметры:
        ----------
        tool_name : str
            Имя вызываемого инструмента.
        args : dict
            Аргументы, необходимые для выполнения инструмента.

        Возвращает:
        -----------
        dict
            Результат работы выбранного инструмента.
        """
        args = args or {}
        Log.debug(f"[Tools] Вызов инструмента: {tool_name}, args: {args}")

        # ------------------------
        # store_code — сохранить файл
        # ------------------------
        if tool_name == "store_code":
            filename = args.get("filename", "solution.py")
            code = args.get("code") or args.get("content") or ""
            result = self.ws.store_code(filename, code)
            Log.info(f"[Tools] Файл '{filename}' сохранён, символов: {result['chars']}")
            return result

        # ------------------------
        # read_code — получить содержимое файла
        # ------------------------
        if tool_name == "read_code":
            filename = args.get("filename", "solution.py")
            result = self.ws.read_code(filename)
            Log.info(f"[Tools] Прочитан файл '{filename}', символов: {len(result.get('code',''))}")
            return result

        # ------------------------
        # run_python — выполнить произвольный код
        # ------------------------
        if tool_name == "run_python":
            code = args.get("code", "")
            result = self.ws.run_python(code)
            if result.get("error"):
                Log.error(f"[Tools] Ошибка при выполнении кода: {result['error']}")
            else:
                Log.info(f"[Tools] Код выполнен успешно, вывод: {result['stdout'][:200]}")
            return result

        # ------------------------
        # run_tests — выполнить решение + тесты
        # ------------------------
        if tool_name == "run_tests":
            filename = args.get("filename", "solution.py")
            tests_code = args.get("tests_code", "")
            test_file = args.get("test_file", "")
            
            # Подробное логирование параметров для отладки
            Log.debug(f"[Tools] run_tests вызван с параметрами: filename={filename}, test_file={test_file}, tests_code_length={len(tests_code)}")
            
            # Проверка существования test_file перед запуском
            if test_file and test_file not in self.ws.files:
                return {
                    "passed": False, 
                    "error": f"Тестовый файл {test_file} не существует"
                }
            
            result = self.ws.run_tests(filename, tests_code, test_file)
            
            if result.get("passed"):
                Log.info(f"[Tools] Тесты файла '{filename}' пройдены успешно.")
                # Добавим результаты тестов в broadcast для информирования всех агентов
                Log.info(f"[Tools] TESTS PASSED: Все тесты успешно пройдены! Функция работает корректно.")
            else:
                error_msg = result.get('error','')
                Log.warn(f"[Tools] Тесты файла '{filename}' не пройдены, ошибка: {error_msg[:200]}")
            
            return result

        # ------------------------
        # lint_code — базовый линтер
        # ------------------------
        if tool_name == "lint_code":
            code = args.get("code", "")
            issues = []
            if "    " in code and "\t" in code:
                issues.append("Смешение табуляций и пробелов")
            result = {"issues": issues, "issue_count": len(issues)}
            Log.info(f"[Tools] Линтинг кода завершён, найдено проблем: {len(issues)}")
            return result

        # ------------------------
        # generate_tests — передача LLM-агенту создания тестов
        # ------------------------
        if tool_name == "generate_tests":
            # Агент через LLM сам должен сформировать тесты на основе 
            # описания задачи и файла решения
            function_name = args.get("function_name", "")
            test_file_name = args.get("test_file_name", "tests.py")
            test_code = args.get("test_code", "")
            
            if not test_code:
                return {
                    "error": "Необходимо предоставить код тестов в параметре test_code"
                }
            
            result = self.ws.store_code(test_file_name, test_code)
            Log.info(f"[Tools] Сохранены тесты в файл '{test_file_name}', символов: {result['chars']}")
            return {
                "message": f"Тесты сохранены в {test_file_name}",
                "file_name": test_file_name,
                "chars": result['chars'],
                "tests_code": test_code  # Для совместимости с существующим кодом
            }

        # ------------------------
        # неизвестный инструмент
        # ------------------------
        error_msg = f"неизвестный инструмент {tool_name}"
        Log.error(f"[Tools] {error_msg}")
        return {"error": error_msg}

