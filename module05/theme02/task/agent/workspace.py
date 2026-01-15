import sys
import traceback
import difflib
from io import StringIO
from typing import Any, Dict, List, Optional
from log import Log

class Workspace:
    """
    Виртуальная рабочая среда многоагентной системы.

    Данный класс моделирует мини-файловую систему и безопасное окружение для 
    выполнения Python-кода. Основная задача Workspace — предоставить агентам 
    (coder, tester, reviewer) возможность:

    1. Создавать и изменять виртуальные файлы с кодом.
    2. Читать содержимое файлов.
    3. Исполнять Python-код в песочнице (sandbox) с ограниченными возможностями.
    4. Запускать тесты, комбинируя код и тестовые сценарии.
    5. Хранить внутреннее состояние (memory), если это требуется логике агентов.

    Такой подход имитирует полноценную рабочую среду программиста, но без 
    взаимодействия с реальной файловой системой. Это гарантирует безопасность 
    и предсказуемость выполнения.
    """

    def __init__(self):
        """
        Инициализирует пустую виртуальную среду.

        Атрибуты:
            files (Dict[str, str]):
                Словарь, где ключ — имя файла, значение — его текстовое содержимое.

            memory (Dict[str, Any]):
                Вспомогательное хранилище произвольных данных.
                Может использоваться агентами для запоминания промежуточных
                состояний, результатов анализа, подсказок и др.

        Важно:
            Виртуальные файлы существуют только в памяти процесса.
            На реальный диск ничего не записывается.
        """
        self.files: Dict[str, str] = {}
        self.memory: Dict[str, Any] = {}

    def store_code(self, filename: str, code: str) -> Dict[str, Any]:
        """
        Сохраняет (или перезаписывает) содержимое виртуального файла.

        Параметры:
            filename (str):
                Имя файла (например: "solution.py").
            code (str):
                Новый текст файла.

        Поведение:
            • Если файл ранее существовал — вычисляется diff (разница между старым и новым содержимым).
            • Проверяется, что новый код не пустой, если старый файл не был пустым.
            • Новый код заменяет старый полностью.
            • Возвращается информация о количестве символов и вычисленный diff.

        Возвращает:
            dict:
            {
                "message": "stored <filename>",
                "filename": filename,
                "chars": <кол-во символов в новом файле>,
                "diff": <строка с unix-стилем diff>
            }

        Зачем нужен diff:
            Агент reviewer или orchestrator может использовать diff для анализа изменений,
            не перечитывая весь файл.

        Примечание:
            Это *не* запись в реальную файловую систему — всё хранится в self.files.
        """
        prev = self.files.get(filename, "")
        
        # Защита от перезаписи непустого файла пустым содержимым
        if prev and not code.strip() and filename == "solution.py":
            Log.warn(f"Попытка перезаписать непустой файл {filename} пустым содержимым. Операция отклонена.")
            return {
                "message": f"error: отказано в перезаписи {filename}",
                "filename": filename,
                "error": "Нельзя перезаписывать непустой файл solution.py пустым содержимым",
                "chars": 0,
                "diff": ""
            }
        
        # Создаем резервную копию важных файлов в memory
        if filename == "solution.py" and code.strip():
            self.memory["backup_solution"] = code
        
        # Сохраняем новый код
        self.files[filename] = code

        diff = "\n".join(
            difflib.unified_diff(
                prev.splitlines(),
                code.splitlines(),
                fromfile=f"prev:{filename}",
                tofile=f"new:{filename}",
                lineterm=""
            )
        )

        Log.info(f"Файл '{filename}' сохранен, символов: {len(code)}")

        return {
            "message": f"stored {filename}",
            "filename": filename,
            "chars": len(code),
            "diff": diff
        }

    def read_code(self, filename: str) -> Dict[str, Any]:
        """
        Возвращает содержимое виртуального файла.

        Параметры:
            filename (str):
                Имя файла, который нужно прочитать.

        Возвращает:
            dict:
            {
                "filename": filename,
                "code": <текст файла или пустая строка, если файл не существует>
            }

        Примечание:
            Метод не генерирует ошибок при отсутствии файла — просто возвращает пустой код.
        """
        return {"filename": filename, "code": self.files.get(filename, "")}

    def run_python(self, code: str, timeout_seconds: float = 3.0) -> Dict[str, Any]:
        """
        Выполняет переданный Python-код в ограниченной среде (sandbox).

        Параметры:
            code (str):
                Строка с Python-кодом для выполнения.
            timeout_seconds (float):
                (Планируется для будущих версий) лимит времени на выполнение.

        Поведение:
            • Перехватывает stdout (все print выводы).
            • Разрешает только безопасный набор встроенных функций (print, range, len, int, float и т.п.).
            • Полностью запрещает импорт модулей и доступ к системным ресурсам.
            • В случае ошибки возвращает трассировку (traceback).

        Возвращает:
            dict:
            {
                "stdout": <вывод программы>,
                "error": <текст ошибки или пустая строка>
            }

        Зачем нужна песочница:
            — Исключает возможность выполнения вредоносного или опасного кода.
            — Предотвращает доступ к диску, сети и запрещённым встроенным функциям.
        """
        captured = StringIO()
        old_out = sys.stdout
        sys.stdout = captured
        out = {"stdout": "", "error": ""}

        try:
            allowed = {
                "print": print, "range": range, "len": len, "sum": sum,
                "min": min, "max": max, "abs": abs,
                "int": int, "float": float, "str": str, "bool": bool,
                "list": list, "dict": dict, "set": set, "tuple": tuple
            }

            exec_globals = {"__builtins__": allowed}
            exec_locals = {}

            exec(code, exec_globals, exec_locals)

            out["stdout"] = captured.getvalue()

        except Exception:
            out["error"] = traceback.format_exc()
            Log.error(out["error"])

        finally:
            sys.stdout = old_out

        return out

    def run_tests(self, filename: str, tests_code: str = "", test_file: str = "") -> Dict[str, Any]:
        """
        Выполняет тесты для указанного файла.

        Параметры:
            filename (str):
                Имя файла, код которого нужно тестировать.
            tests_code (str, optional):
                Набор Python-тестов (чаще всего — assert выражения).
                Можно передать напрямую или через файл test_file.
            test_file (str, optional):
                Имя файла с тестами. Если указано, тесты берутся из этого файла.

        Поведение:
            • Если файла с кодом нет — возвращает ошибку.
            • Если указан test_file, извлекает тесты из этого файла.
            • Если указан tests_code, использует его напрямую.
            • Объединяет основной код и тестовый код в одну строку.
            • Выполняет их через run_python().
            • Считает тесты пройденными, если не возникло ошибок.

        Возвращает:
            dict:
            {
                "passed": True/False,
                "stdout": <вывод программы>,
                "error": <текст ошибки или пустая строка>
            }

        Применение:
            Агент tester вызывает этот метод после генерации тестов.
            Если тесты прошли успешно — orchestrator может завершить работу системы.
        """
        # Проверяем, существует ли файл solution.py и не пустой ли он
        code = self.files.get(filename, "")
        if not code:
            # Пытаемся восстановить из резервной копии, если она есть
            if filename == "solution.py" and "backup_solution" in self.memory:
                Log.warn(f"Восстанавливаем {filename} из резервной копии")
                code = self.memory["backup_solution"]
                self.files[filename] = code
            else:
                return {
                    "passed": False,
                    "stdout": "",
                    "error": f"Файл {filename} не найден или пуст"
                }

        # Проверка функции в solution.py
        if filename == "solution.py":
            if "def is_prime" not in code and "def quick_sort" not in code:
                return {
                    "passed": False,
                    "stdout": "",
                    "error": f"В файле {filename} не обнаружена ожидаемая функция (is_prime или quick_sort)"
                }

        # Если указан файл с тестами, берем код тестов из него
        if test_file and test_file in self.files:
            tests_code = self.files.get(test_file, "")
            if not tests_code:
                return {
                    "passed": False,
                    "stdout": "",
                    "error": f"Файл с тестами {test_file} существует, но пуст"
                }
            
            Log.info(f"Используются тесты из файла '{test_file}'")
            
            # Проверка, если тесты содержат дубликат функции из solution.py
            # Это частая проблема, когда LLM копирует функцию в тесты
            import re
            function_name = re.search(r'def\s+(\w+)', code)
            if function_name and function_name.group(1) in tests_code:
                # Модифицируем тесты, чтобы они импортировали функцию вместо дубликата
                module_name = filename.replace('.py', '')
                tests_code = f"from {module_name} import {function_name.group(1)}\n" + tests_code
                # Удаляем определение функции из тестового файла
                tests_code = re.sub(r'def\s+' + function_name.group(1) + r'.*?return.*?\n\n', '', tests_code, flags=re.DOTALL)
                Log.info(f"Тесты модифицированы для импорта функции {function_name.group(1)} из {filename}")
                
        elif not tests_code:
            return {
                "passed": False,
                "stdout": "",
                "error": "Не предоставлен код тестов ни через параметр tests_code, ни через test_file"
            }

        # Если тесты используют unittest, запускаем их отдельно
        if "unittest" in tests_code and "class Test" in tests_code:
            # Извлекаем код функции из файла решения
            function_code = code.strip()
            
            # Проверяем наличие импорта функции в тестах и заменяем его
            function_name = re.search(r'def\s+(\w+)', code)
            if function_name and function_name.group(1):
                # Заменяем импорт на прямое определение функции
                tests_code = re.sub(
                    f"from solution import {function_name.group(1)}", 
                    function_code, 
                    tests_code
                )
                Log.info(f"Заменен импорт функции {function_name.group(1)} прямым определением")
                
                # Если в тесте всё ещё присутствует импорт, добавляем функцию вначале
                if "from solution import" in tests_code:
                    tests_code = function_code + "\n\n" + tests_code.replace(f"from solution import {function_name.group(1)}", "")
                    Log.info(f"Добавлено прямое определение функции {function_name.group(1)} в тесты")
            
            # Сохраняем модифицированные тесты во временный файл
            temp_test_file = "_temp_test_run.py"
            self.files[temp_test_file] = tests_code
            
            # Подготавливаем код для запуска юнит-тестов без импорта
            run_code = f"import unittest\n\n{function_code}\n\n{tests_code}\n\nif __name__ == '__main__':\n    unittest.main(argv=['first-arg-is-ignored'], exit=False)"
            res = self.run_python(run_code)
        else:
            # Для обычных assert-тестов просто объединяем код
            combined = code + "\n\n" + tests_code
            res = self.run_python(combined)
            
        passed = res["error"] == ""

        Log.info(f"Тесты файла '{filename}' {'пройдены' if passed else 'не пройдены'}")

        return {"passed": passed, **res}
