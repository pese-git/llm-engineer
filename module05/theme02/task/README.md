# Мультиагентный пайплайн с планировщиком: реализация на Python + OpenAI

## 🚩 Суть и архитектура

Система реализует полноценную мультиагентную команду для автоматизации цикла CODER→TESTER→REVIEWER (и возвратов), где ВСЕ baton и маршрутизация шагов централизовано управляются PlannerAgent (LLM).

- **Роли:**
  - **PlannerAgent** — Централизованный планировщик, анализирует историю, решает кому baton и какое действие (LLM).
  - **CoderAgent** — реализует/сохраняет код.
  - **TesterAgent** — генерирует тесты, запускает их (run_tests).
  - **ReviewerAgent** — отвечает за стиль/линтинг.
- **Вся коммуникация через message bus (Bus, BusMessage)**, каждый агент получает baton и делает ровно один шаг, инструмент вызывается реально.


## 💡 Взаимодействие и протокол

1. **Planner** ставит задачу coder-у → сохраняет решение.
2. **Planner** передаёт тестеру → генерирует и сохраняет тесты.
3. **Planner** ещё раз тестеру → запускает run_tests (автоматически анализирует результат и решает дальнейшую судьбу).
4. **Если ошибки** — Planner возвращает baton codеру.
5. **После успеха тестов** — Planner передаёт reviewer → lint_code.
6. **После успеха lint** — Planner отправляет manager `finish`.

- 💬 **Вся маршрутизация (ask_agent, use_tool, finish) решается LLM в Planner**, а другие агенты — просто рабочие исполнители.

---

## 🔨 Инструменты

- `store_code`: Сохраняет кодовый файл (реально создаёт файл).
- `read_code`: Читает файл, возвращает содержимое.
- `run_tests`: Собирает два файла, запускает через unittest (sandboxed), анализирует результат.
- `lint_code`: Проверяет стиль, возвращает issues или "Стиль кода в порядке".
- `summarize_text`: (опционально) — сокращение текстов, резюме.
- `run_python`: Выполняет произвольный python-код (sandbox).

---

## 🧩 SGR (Structured Output) — схемы данных

Все данные структурированы на pydantic (см. sgr.py):
- `AskAgent`: {"action": "ask_agent", "target": "...", "message": "..."}
- `UseTool`: {"action": "use_tool", "tool_name": ..., "args": ...}
- `Finish`: {"action": "finish", "summary": ...}
- `BusMessage`: для инфраструктуры bus/log

---

## 🔎 Пример лога одного успешного запуска

<details>
<summary>[TRACE] Baton у planner: {'action': 'ask_agent'} :: content=Реализовать функцию is_prime(n: int) -> bool, которая проверяет, является ли число простым.</summary>

```
[TRACE] Baton у planner: {'action': 'ask_agent'} :: content=Реализовать функцию is_prime(n: int) -> bool, которая проверяет, является ли число простым.
[TRACE] Длина истории: 1
[TRACE] Planner думает… (вызов LLM)
[TRACE] Planner выбрал: coder, message=Реализуй функцию is_prime(n: int) -> bool, которая проверяет, является ли число простым, и сохрани её как solution.py.

[TRACE] Baton у coder: {'action': 'ask_agent'} :: content=Реализуй функцию is_prime(n: int) -> bool, которая проверяет, является ли число простым, и сохрани её как solution.py.
[TRACE] Длина истории: 2
[TRACE] Агент coder: выполняет decide…
[TRACE] Агент coder: вызывает инструмент store_code
[TRACE] Результат инструмента: {'status': 'ok', 'message': 'Код для solution.py сохранён.'}

[TRACE] Baton у planner: {'action': 'use_tool', 'tool': 'store_code', 'args': {'filename': 'solution.py', 'code': 'def is_prime(n: int) -> bool:\n    if n <= 1:\n        return False\n    if n <= 3:\n        return True\n    if n % 2 == 0 or n % 3 == 0:\n        return False\n    i = 5\n    while i * i <= n:\n        if n % i == 0 or n % (i + 2) == 0:\n            return False\n        i += 6\n    return True'}} :: content={'status': 'ok', 'message': 'Код для solution.py сохранён.'}
[TRACE] Длина истории: 3
[TRACE] Planner думает… (вызов LLM)
[TRACE] Planner выбрал: tester, message=Сгенерируй юнит-тесты на solution.py, сохрани их как test_solution.py, без комментариев и markdown.

[TRACE] Baton у tester: {'action': 'ask_agent'} :: content=Сгенерируй юнит-тесты на solution.py, сохрани их как test_solution.py, без комментариев и markdown.
[TRACE] Длина истории: 4
[TRACE] Агент tester: выполняет decide…
[TRACE] Агент tester: вызывает инструмент store_code
[TRACE] Результат инструмента: {'status': 'ok', 'message': 'Код для test_solution.py сохранён.'}

[TRACE] Baton у planner: {'action': 'use_tool', 'tool': 'store_code', 'args': {'filename': 'test_solution.py', 'code': '\nimport unittest\nfrom solution import is_prime\n\nclass TestIsPrime(unittest.TestCase):\n    def test_prime_numbers(self):\n        self.assertTrue(is_prime(2))\n        self.assertTrue(is_prime(3))\n        self.assertTrue(is_prime(5))\n        self.assertTrue(is_prime(7))\n        self.assertTrue(is_prime(11))\n        self.assertTrue(is_prime(13))\n        self.assertTrue(is_prime(17))\n        self.assertTrue(is_prime(19))\n        self.assertTrue(is_prime(23))\n\n    def test_non_prime_numbers(self):\n        self.assertFalse(is_prime(1))\n        self.assertFalse(is_prime(0))\n        self.assertFalse(is_prime(-1))\n        self.assertFalse(is_prime(4))\n        self.assertFalse(is_prime(6))\n        self.assertFalse(is_prime(8))\n        self.assertFalse(is_prime(9))\n        self.assertFalse(is_prime(10))\n        self.assertFalse(is_prime(12))\n\n    def test_large_prime_number(self):\n        self.assertTrue(is_prime(7919))\n\n    def test_large_non_prime_number(self):\n        self.assertFalse(is_prime(8000))\n\nif __name__ == "__main__":\n    unittest.main()\n'}} :: content={'status': 'ok', 'message': 'Код для test_solution.py сохранён.'}
[TRACE] Длина истории: 5
[TRACE] Planner думает… (вызов LLM)
[TRACE] Planner выбрал: tester, message=Выполни инструмент run_tests (solution.py, test_solution.py)

[TRACE] Baton у tester: {'action': 'ask_agent'} :: content=Выполни инструмент run_tests (solution.py, test_solution.py)
[TRACE] Длина истории: 6
[TRACE] Агент tester: выполняет decide…
[TRACE] Агент tester: вызывает инструмент run_tests
[TRACE] Результат инструмента: {'status': 'ok', 'message': 'Все тесты пройдены!', 'output': 'test_large_non_prime_number (__main__.TestIsPrime.test_large_non_prime_number) ... ok\ntest_large_prime_number (__main__.TestIsPrime.test_large_prime_number) ... ok\ntest_non_prime_numbers (__main__.TestIsPrime.test_non_prime_numbers) ... ok\ntest_prime_numbers (__main__.TestIsPrime.test_prime_numbers) ... ok\n\n----------------------------------------------------------------------\nRan 4 tests in 0.000s\n\nOK\n'}

[TRACE] Baton у planner: {'action': 'use_tool', 'tool': 'run_tests', 'args': {'filename': 'solution.py', 'test_file': 'test_solution.py'}} :: content={'status': 'ok', 'message': 'Все тесты пройдены!', 'output': 'test_large_non_prime_number (__main__.TestIsPrime.test_large_non_prime_number) ... ok\ntest_large_prime_number (__main__.TestIsPrime.test_large_prime_number) ... ok\ntest_non_prime_numbers (__main__.TestIsPrime.test_non_prime_numbers) ... ok\ntest_prime_numbers (__main__.TestIsPrime.test_prime_numbers) ... ok\n\n----------------------------------------------------------------------\nRan 4 tests in 0.000s\n\nOK\n'}
[TRACE] Длина истории: 7
[TRACE] Planner думает… (вызов LLM)
[TRACE] Planner выбрал: reviewer, message=Проверь стиль кода (lint_code).

[TRACE] Baton у reviewer: {'action': 'ask_agent'} :: content=Проверь стиль кода (lint_code).
[TRACE] Длина истории: 8
[TRACE] Агент reviewer: выполняет decide…
[TRACE] Агент reviewer: вызывает инструмент lint_code
[TRACE] Результат инструмента: {'status': 'ok', 'message': 'Стиль кода в порядке.'}

[TRACE] Baton у planner: {'action': 'use_tool', 'tool': 'lint_code', 'args': {'code': 'def is_prime(n: int) -> bool:\n    if n <= 1:\n        return False\n    if n <= 3:\n        return True\n    if n % 2 == 0 or n % 3 == 0:\n        return False\n    i = 5\n    while i * i <= n:\n        if n % i == 0 or n % (i + 2) == 0:\n            return False\n        i += 6\n    return True'}} :: content={'status': 'ok', 'message': 'Стиль кода в порядке.'}
[TRACE] Длина истории: 9
[TRACE] Planner думает… (вызов LLM)

=== Process finished! (Planner дал finish) ===


[Файлы в рабочем пространстве]:

--- solution.py ---
def is_prime(n: int) -> bool:
    if n <= 1:
        return False
    if n <= 3:
        return True
    if n % 2 == 0 or n % 3 == 0:
        return False
    i = 5
    while i * i <= n:
        if n % i == 0 or n % (i + 2) == 0:
            return False
        i += 6
    return True

--- test_solution.py ---

import unittest
from solution import is_prime

class TestIsPrime(unittest.TestCase):
    def test_prime_numbers(self):
        self.assertTrue(is_prime(2))
        self.assertTrue(is_prime(3))
        self.assertTrue(is_prime(5))
        self.assertTrue(is_prime(7))
        self.assertTrue(is_prime(11))
        self.assertTrue(is_prime(13))
        self.assertTrue(is_prime(17))
        self.assertTrue(is_prime(19))
        self.assertTrue(is_prime(23))

    def test_non_prime_numbers(self):
        self.assertFalse(is_prime(1))
        self.assertFalse(is_prime(0))
        self.assertFalse(is_prime(-1))
        self.assertFalse(is_prime(4))
        self.assertFalse(is_prime(6))
        self.assertFalse(is_prime(8))
        self.assertFalse(is_prime(9))
        self.assertFalse(is_prime(10))
        self.assertFalse(is_prime(12))

    def test_large_prime_number(self):
        self.assertTrue(is_prime(7919))

    def test_large_non_prime_number(self):
        self.assertFalse(is_prime(8000))

if __name__ == "__main__":
    unittest.main()


[Лог]
manager -> planner: ask_agent Реализовать функцию is_prime(n: int) -> bool, которая проверяет, является ли число простым.

planner -> coder: ask_agent Реализуй функцию is_prime(n: int) -> bool, которая проверяет, является ли число простым, и сохрани её как solution.py.

coder -> planner: use_tool {'status': 'ok', 'message': 'Код для solution.py сохранён.'}

planner -> tester: ask_agent Сгенерируй юнит-тесты на solution.py, сохрани их как test_solution.py, без комментариев и markdown.

tester -> planner: use_tool {'status': 'ok', 'message': 'Код для test_solution.py сохранён.'}

planner -> tester: ask_agent Выполни инструмент run_tests (solution.py, test_solution.py)

tester -> planner: use_tool {'status': 'ok', 'message': 'Все тесты пройдены!', 'output': 'test_large_non_prime_number (__main__.TestIsPrime.test_large_non_prime_number) ... ok\ntest_large_prime_number (__main__.TestIsPrime.test_large_prime_number) ... ok\ntest_non_prime_numbers (__main__.TestIsPrime.test_non_prime_numbers) ... ok\ntest_prime_numbers (__main__.TestIsPrime.test_prime_numbers) ... ok\n\n----------------------------------------------------------------------\nRan 4 tests in 0.000s\n\nOK\n'}

planner -> reviewer: ask_agent Проверь стиль кода (lint_code).

reviewer -> planner: use_tool {'status': 'ok', 'message': 'Стиль кода в порядке.'}

planner -> manager: finish Все проверки пройдены, пайплайн завершён.
```
</details>

---

## 📂 Артефакты

- Все файлы (`solution.py`, `test_solution.py`) реально создаются в memory-workspace.
- Тесты исполняются реально (unittest), результат в логе BUS.

---

## 📋 Ограничения и метрики

- Маршрутизация и возвраты — полностью через PlannerAgent (LLM).
- Пайплайн может циклично возвращаться на coder, tester, reviewer.
- Чёткая SGR-валидация на каждом шаге.
- Все файлы-побочные эффекты реально создаются.

---

## 🏁 Как запустить

1. Установите зависимости (`openai`, `pydantic` и др.).
2. Пропишите свой OPENAI_API_KEY в .env или переменных окружения.
3. Запустите:

```bash
.venv/bin/python module05/theme02/task/native/main.py
```

---

## 🎬 Видео прогонки пайплайна

[Смотреть демонстрацию мультиагентного сценария (.mov)](./mulitiagent.mov)

<details>
<summary>Встроенное видео (требует поддержки markdown на платформе):</summary>

```html
<video controls width="600">
  <source src="./mulitiagent.mov" type="video/mp4">
  Your browser does not support the video tag.
</video>
```
</details>