
import os
import time
import json
import traceback
from typing import Optional
from pydantic import BaseModel
from log import Log

#os.environ["OPENROUTER_API_KEY"]="Your key here"

DEFAULT_MODEL = "qwen/qwen3-30b-a3b-instruct-2507"  # по умолчанию, но можно использовать любую совместимую модель
client = None

from openai import OpenAI

# Приоритет: LLM_API_URL + LLM_API_KEY > OPENROUTER_API_KEY > fallback
llm_api_url = os.environ.get("LLM_API_URL")
llm_api_key = os.environ.get("LLM_API_KEY")
openrouter_api_key = os.environ.get("OPENROUTER_API_KEY")

if llm_api_url and llm_api_key:
    try:
        client = OpenAI(
            base_url=llm_api_url.rstrip("/"),
            api_key=llm_api_key,
        )
        DEFAULT_MODEL = "gpt-4.1"
        Log.info(f"[LLM] Используется openai/openrouter-совместимый endpoint: {llm_api_url}")
    except Exception as e:
        raise RuntimeError(f"[LLM] Не удалось инициализировать endpoint {llm_api_url}: {e}")
elif openrouter_api_key:
    try:
        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=openrouter_api_key,
        )
        DEFAULT_MODEL = "qwen/qwen3-30b-a3b-instruct-2507"
        Log.info("[LLM] Используется OpenRouter endpoint с заданным ключом.")
    except Exception as e:
        raise RuntimeError(f"[LLM] Не удалось инициализировать OpenRouter: {e}")
else:
    client = None
    Log.warn("[LLM] LLM_API_URL/KEY и OPENROUTER_API_KEY не заданы. Активирован fallback режим!")

# ---------------------------
# LLM caller with JSON schema; retries on invalid JSON
# If OpenRouter is not available, fall back to deterministic mock agent behavior.
# ---------------------------

def call_llm_with_schema(prompt: str, response_model: BaseModel, system_prompt: Optional[str] = None,
                         max_retries: int = 3, temperature: float = 0.2) -> BaseModel:
    """
    Универсальный вызов LLM с жёсткой JSON-схемой и механизмом повторных попыток.

    Функция отправляет запрос к модели через openrouter_client и ожидает,
    что LLM вернёт корректный JSON, соответствующий заданной Pydantic-схеме
    (response_model).  

    Возможности:
    ------------
    1. **Строгое требование JSON по схеме**
       LLM получает инструкцию вернуть JSON-объект, соответствующий
       модели response_model.

    2. **Автоматические повторы при ошибках**
       Если LLM вернул непарсибельный JSON или объект, не соответствующий схеме,
       выполняется до `max_retries` повторов с уточняющими сообщениями.

    3. **Fallback, если OpenRouter недоступен**
       Если openrouter_client = None, вызов полностью переключается
       на локальный детерминированный мок — fallback_llm(), чтобы можно было
       тестировать логику агентов без интернета.

    4. **Автоматическая очистка от ```json ... ```**
       Функция _extract_json_from_text() пытается извлечь JSON даже если
       LLM вернул текст с Markdown-оформлением.

    Параметры:
    ----------
    prompt : str
        Основной пользовательский запрос для LLM.

    response_model : BaseModel
        Pydantic-модель, описывающая структуру ожидаемого результата.
        LLM обязан вернуть JSON, который ей соответствует.

    system_prompt : Optional[str]
        Системная подсказка, управляющая поведением LLM.

    max_retries : int
        Максимальное количество попыток получить валидный JSON.

    temperature : float
        "Температура" генерации модели (0–1). Чем меньше — тем более детерминированный вывод.

    Возвращает:
    -----------
    BaseModel
        Экземпляр response_model, успешно извлечённый из ответа LLM.

    Исключения:
    -----------
    RuntimeError  
        Если все попытки завершились невалидным JSON.

    Комментарии:
    ------------
    При неудаче добавляет в сообщения запрос "Пожалуйста, верни строго JSON…",
    что помогает направить LLM к корректному выводу.
    """
    Log.debug(f"[LLM] Вызов с prompt: {prompt[:200]}, system_prompt: {system_prompt}, max_retries: {max_retries}")

    if client is None:
        Log.warn("[LLM] Нет соединения с LLM endpoint, используется fallback_llm")
        return fallback_llm(prompt, response_model, system_prompt)

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    # --- Fix: add required + additionalProperties: False into all objects recursively for API strict schema requirements ---
    def fix_schema(schema):
        if isinstance(schema, dict):
            if schema.get("type") == "object":
                schema["additionalProperties"] = False  # всегда явно False
                # Обеспечить наличие required (пусть пуст, если свойств нет)
                if "properties" in schema:
                    prop_keys = list(schema["properties"].keys())
                    schema["required"] = prop_keys
                    # даже если нет свойств, ставим required=[]
                    for v in schema["properties"].values():
                        fix_schema(v)
                else:
                    schema["properties"] = {}
                    schema["required"] = []
            for v in schema.values():
                fix_schema(v)
        elif isinstance(schema, list):
            for item in schema:
                fix_schema(item)
        return schema
    schema_dict = fix_schema(response_model.model_json_schema())
    last_raw = ""

    for attempt in range(1, max_retries + 1):
        try:
            Log.debug(f"[LLM] Попытка {attempt}")
            resp = client.chat.completions.create(
                model=DEFAULT_MODEL,
                messages=messages,
                response_format={
                    "type": "json_schema",
                    "json_schema": {"name": response_model.__name__, "schema": schema_dict, "strict": True},
                },
                temperature=temperature,
                max_tokens=1500,
            )
            raw = resp.choices[0].message.content or ""
            last_raw = raw
            parsed = _extract_json_from_text(raw)
            Log.info(f"[LLM] Успешно получен JSON на попытке {attempt}")
            return response_model.model_validate_json(parsed)

        except Exception as e:
            Log.error(f"[LLM] Попытка {attempt} не удалась: {e}")
            messages.append({
                "role": "user",
                "content": "Пожалуйста, верни строго JSON по указанной схеме, без пояснений."
            })
            time.sleep(0.3)
            continue

    Log.error(f"[LLM] Все {max_retries} попыток не удались, последний ответ:\n{last_raw}")
    raise RuntimeError(
        f"LLM did not return valid JSON after {max_retries} attempts. Last raw:\n{last_raw}"
    )


def _extract_json_from_text(s: str) -> str:
    """
    Пытается корректно извлечь JSON даже из обёрнутого в Markdown текста.

    LLM иногда возвращает результат в формате:

        ```json
        { ... }
        ```

    или даже с произвольным текстом до и после JSON.  
    Эта функция:

    1. Удаляет блоковые кавычки ``` ... ``` если они есть  
    2. Проверяет, является ли строка валидным JSON  
    3. Если нет — пытается вырезать подстроку между первой '{' и последней '}'  
    4. Если всё равно не удалось — возвращает оригинальный текст для последующей ошибки

    Параметры:
    ----------
    s : str
        Строка, которая может содержать JSON в любом виде.

    Возвращает:
    -----------
    str  
        Строка, которая, вероятно, является валидным JSON.
        (Парсинг JSON будет выполнен вызывающим кодом.)
    """
    s = (s or "").strip()
    Log.debug(f"[LLM] Извлечение JSON из текста длиной {len(s)}")

    if s.startswith("```"):
        lines = s.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        s = "\n".join(lines).strip()
        Log.debug(f"[LLM] Удалены тройные кавычки, длина после очистки: {len(s)}")

    try:
        json.loads(s)
        return s
    except Exception:
        pass

    first = s.find('{')
    last = s.rfind('}')
    if first != -1 and last != -1 and last > first:
        cand = s[first:last+1]
        try:
            json.loads(cand)
            Log.debug(f"[LLM] JSON успешно извлечён из подстроки")
            return cand
        except Exception:
            pass

    Log.warn("[LLM] Не удалось извлечь корректный JSON, возвращается оригинал")
    return s


def fallback_llm(prompt: str, response_model: BaseModel, system_prompt: Optional[str]):
    """
    Детерминированный локальный мок LLM для автономного тестирования системы.

    Данный режим используется, если openrouter_client == None.
    То есть система работает полностью оффлайн, но логика агентов остаётся.

    Задачи fallback-режима:
    ----------------------
    • позволить тестировать мультиагентную архитектуру без доступа в интернет  
    • вернуть валидный JSON, соответствующий response_model  
    • имитировать поведение агентов на основе простых эвристик  

    Поведение:
    ----------
    • Если в prompt упоминается store_code / write code / implement → формируется UseTool
    • Если встречается "fib" → генерируется код решения задачи FIB
    • Если встречаются слова test / tests → генерируем команду generate_tests
    • В остальных случаях — обычный Reply("ack")

    Параметры:
    ----------
    prompt : str
        Текстовый запрос "от пользователя".

    response_model : BaseModel
        Модель, которую необходимо вернуть.

    system_prompt : Optional[str]
        (не используется, но передаётся)

    Возвращает:
    -----------
    BaseModel
        Заполненная структура, строго соответствующая JSON-схеме.
    """
    text = (prompt or "").lower()
    Log.debug(f"[LLM fallback] Вызов с prompt: {prompt[:200]}")

    if "store_code" in text or "write code" in text or "implement" in text or "fib" in text:
        if "fib" in text:
            code = (
                "def fib(n: int) -> int:\n"
                "    if n <= 1:\n"
                "        return n\n"
                "    a, b = 0, 1\n"
                "    for _ in range(2, n + 1):\n"
                "        a, b = b, a + b\n"
                "    return b\n"
            )
            obj = {
                "step": {
                    "action": "use_tool",
                    "tool_name": "store_code",
                    "args": {"filename": "solution.py", "code": code}
                }
            }
            Log.info("[LLM fallback] Генерируем код FIB для store_code")
            return response_model.model_validate_json(json.dumps(obj))

        obj = {"step": {"action": "reply", "content": "Please provide code or clarify requirements."}}
        Log.info("[LLM fallback] Генерируем fallback reply для coder")
        return response_model.model_validate_json(json.dumps(obj))

    if "run_tests" in text or "tests" in text or "test" in text:
        obj = {
            "step": {
                "action": "use_tool",
                "tool_name": "generate_tests",
                "args": {"func_name": "fib"}
            }
        }
        Log.info("[LLM fallback] Генерируем команду generate_tests для tester")
        return response_model.model_validate_json(json.dumps(obj))

    obj = {"step": {"action": "reply", "content": "ack"}}
    Log.info("[LLM fallback] Генерируем default reply ack")
    return response_model.model_validate_json(json.dumps(obj))
